# lv2_module3 — HSV 설정값에 따른 Mask·검출 결과 변화 분석

보고서: [report.md](./report.md)

## 코드 출처

- [`HSV_SUB.py`](./HSV_SUB.py): 수업 `detect_hsv()` 처리(HSV → `inRange` → Opening/Closing → Contour → `min_area` → 최대 1개)를 ROS 2 노드로 옮긴 비전 노드. 이 저장소에서 관리
- 카메라: `realsense2_camera` 패키지 `rs_launch.py`
- 모터 제어 노드는 사용하지 않음

## 실행 환경

| 항목 | 값 |
| --- | --- |
| OS | Ubuntu 24.04.5 LTS |
| ROS 2 | lyrical |
| Python | 3.12.3 |
| OpenCV | 4.6.0 |
| 입력 | Intel RealSense 실시간 Camera, 640x360 @15fps |

## 실행 명령

```bash
ros2 launch realsense2_camera rs_launch.py rgb_camera.color_profile:=640x360x15
```

```bash
python3 lv2_module3/HSV_SUB.py
```

```bash
ros2 run rqt_image_view rqt_image_view --clear-config /camera/camera/color/image_raw
```

```bash
ros2 topic echo /hsv/detection
```

## 설정값 변경·적용 방법

`HSV_SUB.py`는 ROS 2 파라미터를 시작할 때 한 번 읽는다. HSV 범위를 바꾸려면 노드를 종료하고 `--ros-args -p`로 다시 실행한다. `min_area`만은 노드를 띄운 터미널에서 `a`/`b` 키로 실행 중 전환할 수 있다(실험 2용).

| 파라미터 | 기본값 | 의미 |
| --- | --- | --- |
| `lower_hsv` | `[90, 80, 50]` | `inRange` 하한 (H 0~179, S·V 0~255) |
| `upper_hsv` | `[130, 255, 255]` | `inRange` 상한 |
| `min_area` | `300` | 640 너비 기준 최소 Contour 면적(px²), 해상도에 맞춰 `(width/640)^2` 배 |
| `min_area_a` | `300` | `a` 키를 누르면 `min_area`에 넣을 값 (실험 2 기준값 A) |
| `min_area_b` | `1000` | `b` 키를 누르면 `min_area`에 넣을 값 (실험 2 변경값 B) |

```bash
python3 lv2_module3/HSV_SUB.py --ros-args -p lower_hsv:="[90, 150, 50]"
```

시작 로그 `lower=[...] upper=[...] min_area=...`로 적용값을 확인한다.

```bash
python3 lv2_module3/HSV_SUB.py --ros-args -p lower_hsv:="[90, 150, 50]" -p min_area_a:=300 -p min_area_b:=1000
```

키를 누르면 로그에 `[A] min_area=300` / `[B] min_area=1000`이 찍히고 ROS 2 파라미터 `min_area`도 같이 바뀐다(`ros2 param get /hsv_detector min_area`로 확인).

## 발행 토픽

| 토픽 | 타입 | 내용 |
| --- | --- | --- |
| `/hsv/mask` | `sensor_msgs/msg/Image` (mono8) | Opening/Closing 후 Mask (`min_area` 필터 전) |
| `/hsv/detection` | `std_msgs/msg/String` | `detected=True bbox=(...) center=(...) area=... min_area=... candidates=N/T` 또는 `detected=False min_area=... candidates=0/T` |
| `/hsv/overlay` | `sensor_msgs/msg/Image` (bgr8) | 후보 외곽선·면적, 선택 목표 박스·중심점 |

## 결과 파일 위치

```
results/
├── topic_info/                  토픽 목록, topic info --verbose, Raw Image header·encoding·해상도
├── ex1/                         실험 1: S 하한 80(A) vs 150(B) Mask 캡처, 참고 원본, Mask 측정값,
│                                         150에서 빛 반사된 퍽 미검출 Overlay
├── ex2/                         실험 2: min_area 300(A) vs 1000(B) Overlay (근거리 / 원거리 _small)
├── no_target/                   목표 없음: HSV·min_area 조합별 Overlay, /hsv/detection echo 로그
└── overlay_area_readings.txt    Overlay에서 읽은 Contour 면적과 통과·탈락 정리
```
