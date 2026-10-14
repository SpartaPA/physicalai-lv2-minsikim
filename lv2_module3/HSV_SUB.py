#!/usr/bin/env python3
"""HSV 퍽 검출 ROS 2 노드 (기본 버전)

기존 detect_hsv()와 같은 처리:
  카메라 이미지 → HSV → inRange → Opening/Closing → Mask
  → Contour → min_area 이상만 → 가장 큰 것 1개 → 검출 결과

실험 2용: 실행한 터미널에서 키를 누르면 min_area 를 바로 바꿈
  a → min_area_a (기준값 A),  b → min_area_b (변경값 B)
  노드 재시작 없이 같은 장면에서 A/B 를 번갈아 비교하기 위함 (필터 조건 자체는 그대로)
"""
import sys
import termios
import threading
import tty

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import Image
from std_msgs.msg import String


class HsvDetector(Node):

    def __init__(self):
        super().__init__("hsv_detector")

        # 설정값 (기본값 = 기존 코드 상수). 실행할 때 -p 로 바꿈
        self.declare_parameter("lower_hsv", [90, 80, 50])
        self.declare_parameter("upper_hsv", [130, 255, 255])
        self.declare_parameter("min_area", 300)
        self.declare_parameter("min_area_a", 300)
        self.declare_parameter("min_area_b", 1000)
        self.lower = np.array(self.get_parameter("lower_hsv").value, np.uint8)
        self.upper = np.array(self.get_parameter("upper_hsv").value, np.uint8)
        self.min_area = self.get_parameter("min_area").value

        self.bridge = CvBridge()
        self.create_subscription(Image, "/camera/camera/color/image_raw", self.on_image, 10)
        self.pub_mask = self.create_publisher(Image, "/hsv/mask", 10)
        self.pub_det = self.create_publisher(String, "/hsv/detection", 10)
        self.pub_overlay = self.create_publisher(Image, "/hsv/overlay", 10)

        self.get_logger().info(f"lower={self.lower.tolist()} upper={self.upper.tolist()} min_area={self.min_area}")

        # 키 입력으로 min_area 전환 (터미널에서 실행할 때만)
        self.area_presets = {"a": self.get_parameter("min_area_a").value,
                             "b": self.get_parameter("min_area_b").value}
        self.old_term = None
        if sys.stdin.isatty():
            self.old_term = termios.tcgetattr(sys.stdin.fileno())
            self.get_logger().info(f"키 입력: a → min_area={self.area_presets['a']}, "
                                   f"b → min_area={self.area_presets['b']}")
            threading.Thread(target=self.read_keys, daemon=True).start()

    def read_keys(self):
        tty.setcbreak(sys.stdin.fileno())  # Enter 없이 한 글자씩 읽음 (Ctrl+C 는 그대로 동작)
        while rclpy.ok():
            key = sys.stdin.read(1).lower()
            if key in self.area_presets:
                self.set_min_area(key, self.area_presets[key])

    def restore_terminal(self):
        # 키 입력 스레드는 Ctrl+C 때 바로 끝나므로 터미널 설정은 메인에서 되돌림
        if self.old_term is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.old_term)

    def set_min_area(self, key, value):
        # ROS 2 파라미터도 같이 바꿔 ros2 param get 으로 적용값을 확인할 수 있게 함
        self.set_parameters([Parameter("min_area", value=value)])
        self.min_area = value
        self.get_logger().info(f"[{key.upper()}] min_area={self.min_area}")

    def on_image(self, msg):
        frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")

        # 1) Mask 생성
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower, self.upper)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # 2) 검출: 면적 필터 후 가장 큰 것 (기존 코드처럼 640 너비 기준 면적을 해상도에 맞춤)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        threshold = self.min_area * (frame.shape[1] / 640) ** 2
        candidates = [c for c in contours if cv2.contourArea(c) >= threshold]

        # Overlay: min_area 탈락 후보 빨강, 통과 후보 노랑 (면적 표시)
        overlay = frame.copy()
        for c in contours:
            color = (0, 255, 255) if cv2.contourArea(c) >= threshold else (0, 0, 255)
            cx, cy, _, _ = cv2.boundingRect(c)
            cv2.drawContours(overlay, [c], -1, color, 1)
            cv2.putText(overlay, f"{cv2.contourArea(c):.0f}", (cx, max(cy - 3, 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        if candidates:
            target = max(candidates, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(target)
            text = (f"detected=True bbox=({x},{y},{x + w},{y + h}) "
                    f"center=({x + w // 2},{y + h // 2}) area={cv2.contourArea(target):.0f} "
                    f"min_area={self.min_area} candidates={len(candidates)}/{len(contours)}")
            # 선택된 목표: 초록 박스 + 중심점
            cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.circle(overlay, (x + w // 2, y + h // 2), 3, (0, 255, 0), -1)
        else:
            text = f"detected=False min_area={self.min_area} candidates=0/{len(contours)}"

        cv2.putText(overlay, f"detected={bool(candidates)} min_area={self.min_area}", (5, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if candidates else (0, 0, 255), 1)

        # 3) 발행 (Mask·Overlay는 입력과 같은 header → 같은 프레임인지 stamp로 확인)
        mask_msg = self.bridge.cv2_to_imgmsg(mask, "mono8")
        mask_msg.header = msg.header
        self.pub_mask.publish(mask_msg)
        self.pub_det.publish(String(data=text))
        overlay_msg = self.bridge.cv2_to_imgmsg(overlay, "bgr8")
        overlay_msg.header = msg.header
        self.pub_overlay.publish(overlay_msg)


def main():
    rclpy.init()
    node = HsvDetector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.restore_terminal()


if __name__ == "__main__":
    main()