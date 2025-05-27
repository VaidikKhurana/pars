import cv2
import mediapipe as mp
import numpy as np
import open3d as o3d
import threading
import time
import copy
import sys
import tkinter as tk
from tkinter import filedialog

# --- Load 3D model file ---
def get_model_path():
    if len(sys.argv) > 1:
        return sys.argv[1]
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Select 3D Model",
        filetypes=[("GLB files", "*.glb"), ("All files", "*.*")]
    )
    return file_path

model_path = get_model_path()
if not model_path:
    print("No model file selected. Exiting.")
    sys.exit(1)

original_mesh = o3d.io.read_triangle_mesh(model_path)
original_mesh.compute_vertex_normals()
original_mesh.paint_uniform_color([1.0, 1.0, 1.0])

# --- Open3D visualizer ---
vis = o3d.visualization.Visualizer()
vis.create_window(window_name='3D Model Viewer')
vis.get_render_option().background_color = np.array([0.0, 0.0, 0.0])

# --- Gesture & model state ---
rotate_y = 0.0
rotate_x = 0.0
zoom     = 1.0
trans_x  = 0.0
trans_y  = 0.0

# --- Mediapipe setup ---
mp_hands = mp.solutions.hands
hands    = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
cap      = cv2.VideoCapture(0)

# --- Gesture state ---
prev_ix, prev_iy = None, None
base_dist        = None
grab_active      = False
prev_cx, prev_cy = None, None

def hand_loop():
    global rotate_x, rotate_y, zoom, trans_x, trans_y
    global prev_ix, prev_iy, base_dist, grab_active, prev_cx, prev_cy

    while True:
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.flip(frame, 1)
        H, W, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = hands.process(rgb)

        if res.multi_hand_landmarks:
            lm = res.multi_hand_landmarks[0].landmark
            ix, iy = int(lm[8].x * W), int(lm[8].y * H)
            tx, ty = int(lm[4].x * W), int(lm[4].y * H)
            cx, cy = (ix+tx)//2, (iy+ty)//2
            dist = np.hypot(ix-tx, iy-ty)

            if prev_ix is not None:
                dx = ix - prev_ix
                dy = iy - prev_iy
                rotate_y += dx * 0.005
                rotate_x += dy * 0.005
            prev_ix, prev_iy = ix, iy

            if base_dist is None:
                base_dist = dist
            else:
                delta = dist - base_dist
                zoom += delta * 0.001
                zoom = max(0.1, min(3.0, zoom))
                base_dist = dist

            PINCH_THRESH = 40
            if dist < PINCH_THRESH:
                if not grab_active:
                    grab_active = True
                    prev_cx, prev_cy = cx, cy
                else:
                    dx = cx - prev_cx
                    dy = cy - prev_cy
                    trans_x += dx * 0.005
                    trans_y -= dy * 0.005
                    prev_cx, prev_cy = cx, cy
            else:
                grab_active = False
                prev_cx = prev_cy = None
        else:
            prev_ix = prev_iy = None
            base_dist = None
            grab_active = False
            prev_cx = prev_cy = None

        cv2.imshow("Webcam", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

threading.Thread(target=hand_loop, daemon=True).start()

while True:
    vis.clear_geometries()
    mesh = copy.deepcopy(original_mesh)

    R = mesh.get_rotation_matrix_from_xyz((rotate_x, rotate_y, 0))
    mesh.rotate(R, center=mesh.get_center())
    mesh.scale(zoom, center=mesh.get_center())
    mesh.translate((trans_x, trans_y, 0), relative=True)

    vis.add_geometry(mesh)
    vis.poll_events()
    vis.update_renderer()
    time.sleep(0.03)
