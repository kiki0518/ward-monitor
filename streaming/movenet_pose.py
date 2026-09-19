"""MoveNet inference and pose rules adapted from the supplied movenet_test.py.

No camera is opened here. Streaming passes a copy of a camera-native JPEG.
The classification thresholds, coordinate convention and history rules are unchanged.
"""
import math
import time
from collections import Counter, deque

import cv2
import numpy as np

MODEL = '/opt/gopoint-apps/downloads/movenet_quant_vela.tflite'

DELEGATE = '/usr/lib/libethosu_delegate.so'

KEYPOINT_THRESHOLD = 0.2

PRINT_INTERVAL = 1.0

POSE_HISTORY_SIZE = 5

KEYPOINT_NAMES = ['nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear', 'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow', 'left_wrist', 'right_wrist', 'left_hip', 'right_hip', 'left_knee', 'right_knee', 'left_ankle', 'right_ankle']

def midpoint(p1, p2):
    return ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)

def point_distance(p1, p2):
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    return math.sqrt(dx * dx + dy * dy)

def joint_angle(a, b, c):
    """
    Calculate angle ABC in degrees.
    b is the joint.
    """
    ba = np.array([a[0] - b[0], a[1] - b[1]], dtype=np.float32)
    bc = np.array([c[0] - b[0], c[1] - b[1]], dtype=np.float32)
    norm_ba = np.linalg.norm(ba)
    norm_bc = np.linalg.norm(bc)
    if norm_ba < 1e-06 or norm_bc < 1e-06:
        return None
    cos_value = np.dot(ba, bc) / (norm_ba * norm_bc)
    cos_value = np.clip(cos_value, -1.0, 1.0)
    return math.degrees(math.acos(cos_value))

def visible(kp, *names):
    for name in names:
        if name not in kp:
            return False
        if kp[name]['score'] < KEYPOINT_THRESHOLD:
            return False
    return True

def at_least_one_visible(kp, name1, name2):
    return kp[name1]['score'] >= KEYPOINT_THRESHOLD or kp[name2]['score'] >= KEYPOINT_THRESHOLD

def normalize_keypoints(kp):
    """
    Convert MoveNet coordinates into body-centered coordinates.

    Origin:
        hip center = (0, 0)

    X:
        right = positive

    Y:
        up = positive

    Scale:
        shoulder width = 1
    """
    shoulder_ok = at_least_one_visible(kp, 'left_shoulder', 'right_shoulder')
    hip_ok = at_least_one_visible(kp, 'left_hip', 'right_hip')
    if not shoulder_ok or not hip_ok:
        return None
    left_hip_valid = kp['left_hip']['score'] >= KEYPOINT_THRESHOLD
    right_hip_valid = kp['right_hip']['score'] >= KEYPOINT_THRESHOLD
    if left_hip_valid and right_hip_valid:
        hip_center = midpoint((kp['left_hip']['x'], kp['left_hip']['y']), (kp['right_hip']['x'], kp['right_hip']['y']))
    elif left_hip_valid:
        hip_center = (kp['left_hip']['x'], kp['left_hip']['y'])
    else:
        hip_center = (kp['right_hip']['x'], kp['right_hip']['y'])
    left_shoulder_valid = kp['left_shoulder']['score'] >= KEYPOINT_THRESHOLD
    right_shoulder_valid = kp['right_shoulder']['score'] >= KEYPOINT_THRESHOLD
    if left_shoulder_valid and right_shoulder_valid:
        shoulder_width = point_distance((kp['left_shoulder']['x'], kp['left_shoulder']['y']), (kp['right_shoulder']['x'], kp['right_shoulder']['y']))
    elif left_hip_valid and right_hip_valid:
        shoulder_width = point_distance((kp['left_hip']['x'], kp['left_hip']['y']), (kp['right_hip']['x'], kp['right_hip']['y']))
    else:
        return None
    if shoulder_width < 1e-06:
        return None
    normalized = {}
    for name in KEYPOINT_NAMES:
        x = kp[name]['x']
        y = kp[name]['y']
        nx = (x - hip_center[0]) / shoulder_width
        ny = (hip_center[1] - y) / shoulder_width
        normalized[name] = {'x': nx, 'y': ny, 'score': kp[name]['score']}
    return normalized

def classify_pose(kp):
    normalized = normalize_keypoints(kp)
    if normalized is None:
        return {'pose_class': 'unknown', 'base_pose': 'unknown', 'raising_hand': False, 'left_hand_up': False, 'right_hand_up': False, 'left_knee_angle': None, 'right_knee_angle': None, 'normalized': None}
    n = normalized
    left_shoulder_valid = n['left_shoulder']['score'] >= KEYPOINT_THRESHOLD
    right_shoulder_valid = n['right_shoulder']['score'] >= KEYPOINT_THRESHOLD
    if left_shoulder_valid and right_shoulder_valid:
        shoulder_center = midpoint((n['left_shoulder']['x'], n['left_shoulder']['y']), (n['right_shoulder']['x'], n['right_shoulder']['y']))
    elif left_shoulder_valid:
        shoulder_center = (n['left_shoulder']['x'], n['left_shoulder']['y'])
    else:
        shoulder_center = (n['right_shoulder']['x'], n['right_shoulder']['y'])
    torso_dx = abs(shoulder_center[0])
    torso_dy = abs(shoulder_center[1])
    left_hand_up = False
    right_hand_up = False
    if visible(n, 'left_wrist', 'left_shoulder'):
        left_hand_up = n['left_wrist']['y'] > n['left_shoulder']['y'] + 0.2
    if visible(n, 'right_wrist', 'right_shoulder'):
        right_hand_up = n['right_wrist']['y'] > n['right_shoulder']['y'] + 0.2
    raising_hand = left_hand_up or right_hand_up
    if torso_dx > torso_dy * 0.85:
        base_pose = 'lying'
        if raising_hand:
            pose_class = 'raising_hand'
        else:
            pose_class = 'lying'
        return {'pose_class': pose_class, 'base_pose': base_pose, 'raising_hand': raising_hand, 'left_hand_up': left_hand_up, 'right_hand_up': right_hand_up, 'left_knee_angle': None, 'right_knee_angle': None, 'normalized': normalized}
    left_knee_angle = None
    right_knee_angle = None
    if visible(n, 'left_hip', 'left_knee', 'left_ankle'):
        left_knee_angle = joint_angle((n['left_hip']['x'], n['left_hip']['y']), (n['left_knee']['x'], n['left_knee']['y']), (n['left_ankle']['x'], n['left_ankle']['y']))
    if visible(n, 'right_hip', 'right_knee', 'right_ankle'):
        right_knee_angle = joint_angle((n['right_hip']['x'], n['right_hip']['y']), (n['right_knee']['x'], n['right_knee']['y']), (n['right_ankle']['x'], n['right_ankle']['y']))
    valid_knee_angles = []
    if left_knee_angle is not None:
        valid_knee_angles.append(left_knee_angle)
    if right_knee_angle is not None:
        valid_knee_angles.append(right_knee_angle)
    if len(valid_knee_angles) == 0:
        base_pose = 'unknown'
    else:
        avg_knee_angle = sum(valid_knee_angles) / len(valid_knee_angles)
        if avg_knee_angle < 145:
            base_pose = 'sitting'
        else:
            base_pose = 'standing'
    if raising_hand:
        pose_class = 'raising_hand'
    else:
        pose_class = base_pose
    return {'pose_class': pose_class, 'base_pose': base_pose, 'raising_hand': raising_hand, 'left_hand_up': left_hand_up, 'right_hand_up': right_hand_up, 'left_knee_angle': left_knee_angle, 'right_knee_angle': right_knee_angle, 'normalized': normalized}

def get_stable_pose(history):
    if len(history) == 0:
        return 'unknown'
    counter = Counter(history)
    if 'unknown' in counter:
        del counter['unknown']
    if len(counter) == 0:
        return 'unknown'
    return counter.most_common(1)[0][0]


class MoveNetPose:
    """One interpreter, invoked serially by the pose worker only."""

    def __init__(self, model=MODEL, delegate=DELEGATE, interpreter=None):
        if interpreter is None:
            import tflite_runtime.interpreter as tflite
            print('Loading Ethos-U delegate...', flush=True)
            self.delegate = tflite.load_delegate(delegate)
            print('Loading MoveNet model...', flush=True)
            interpreter = tflite.Interpreter(
                model_path=model, experimental_delegates=[self.delegate]
            )
        self.interpreter = interpreter
        interpreter.allocate_tensors()
        self.input_info = interpreter.get_input_details()[0]
        self.output_info = interpreter.get_output_details()[0]
        shape = self.input_info['shape']
        if len(shape) != 4 or shape[0] != 1 or shape[3] != 3:
            raise ValueError(f'Expected model input [1, H, W, 3], got {shape}')
        if tuple(self.output_info['shape']) != (1, 1, 17, 3):
            raise ValueError(f'Expected MoveNet output [1, 1, 17, 3], got {self.output_info["shape"]}')
        self.input_h, self.input_w = int(shape[1]), int(shape[2])
        if self.input_info['dtype'] not in (np.uint8, np.int8, np.float32):
            raise ValueError(f'Unsupported input dtype: {self.input_info["dtype"]}')
        self.history = deque(maxlen=POSE_HISTORY_SIZE)
        print(f'Model input: {self.input_w} x {self.input_h}; dtype: {self.input_info["dtype"]}', flush=True)

    def infer_jpeg(self, jpeg):
        # Decode only this branch. No changes are written back into the shared JPEG.
        frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError('Cannot decode camera JPEG for MoveNet')
        return self.infer_frame(frame)

    def infer_frame(self, frame):
        frame_h, frame_w = frame.shape[:2]
        resized = cv2.resize(frame, (self.input_w, self.input_h))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        dtype = self.input_info['dtype']
        # Preserve the supplied model's preprocessing, including int8 quantization.
        if dtype == np.uint8:
            tensor = rgb.astype(np.uint8)
        elif dtype == np.int8:
            scale, zero_point = self.input_info['quantization']
            tensor = rgb.astype(np.float32)
            if scale != 0:
                tensor = tensor / scale + zero_point
            tensor = np.clip(tensor, -128, 127).astype(np.int8)
        else:
            tensor = rgb.astype(np.float32)
        self.interpreter.set_tensor(self.input_info['index'], np.expand_dims(tensor, axis=0))
        start = time.perf_counter()
        self.interpreter.invoke()
        inference_ms = (time.perf_counter() - start) * 1000
        output = self.interpreter.get_tensor(self.output_info['index'])
        scale, zero_point = self.output_info['quantization']
        if scale != 0 and output.dtype != np.float32:
            output = (output.astype(np.float32) - zero_point) * scale
        if output.shape != (1, 1, 17, 3):
            raise ValueError(f'Unexpected output shape: {output.shape}')
        keypoints = {}
        for name, point in zip(KEYPOINT_NAMES, output[0, 0]):
            y, x, score = map(float, point)
            keypoints[name] = {
                'x': x, 'y': y, 'score': score,
                'pixel_x': int(x * frame_w), 'pixel_y': int(y * frame_h),
            }
        result = classify_pose(keypoints)
        self.history.append(result['pose_class'])
        return {
            **result, 'stable_pose': get_stable_pose(self.history),
            'pose_history': list(self.history), 'keypoints': keypoints,
            'inference_ms': inference_ms, 'frame_width': frame_w, 'frame_height': frame_h,
        }


def print_pose(result):
    lines = [
        '\n========================================',
        f'Inference: {result["inference_ms"]:.2f} ms',
        f'Raw pose: {result["pose_class"]}',
        f'Stable pose: {result["stable_pose"]}',
        f'Base pose: {result["base_pose"]}',
        f'Raising hand: {result["raising_hand"]}',
        f'Left hand up: {result["left_hand_up"]}',
        f'Right hand up: {result["right_hand_up"]}',
        f'Pose history: {result["pose_history"]}',
    ]
    for side in ('left', 'right'):
        angle = result[f'{side}_knee_angle']
        if angle is not None:
            lines.append(f'{side.capitalize()} knee angle: {angle:.1f}')
    normalized = result['normalized']
    if normalized is not None:
        lines.append('\nImportant keypoints:')
        for name in KEYPOINT_NAMES[5:]:
            if 'elbow' not in name:
                point = normalized[name]
                lines.append(f"{name:15s} x={point['x']:.3f} y={point['y']:.3f} score={point['score']:.3f}")
    print('\n'.join(lines), flush=True)
