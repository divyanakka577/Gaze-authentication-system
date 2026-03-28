import cv2
import numpy as np
import face_recognition
import time
from GazeTracking.gaze_tracking import GazeTracking

gaze = GazeTracking()

FACE_MATCH_THRESHOLD = 0.45
FACE_MISSING_TIMEOUT = 3.0
INACTIVITY_TIMEOUT = 5.0
MAX_CONSECUTIVE_BAD_GAZE = 15
FACE_CHECK_INTERVAL = 5


def create_connected_maze_with_display(size=5):
    """Create a simple high-contrast maze for gaze verification."""
    shape = (size * 2 + 1, size * 2 + 1)
    maze = np.ones(shape, dtype=np.uint8) * 255
    visited = np.zeros(shape, dtype=bool)
    start_x, start_y = 1, 1
    stack = [(start_x, start_y)]
    visited[start_y, start_x] = True
    maze_coords = [(start_x, start_y)]

    directions = [(0, 2), (0, -2), (2, 0), (-2, 0)]
    while stack:
        x, y = stack[-1]
        found = False
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if 0 < nx < shape[1] and 0 < ny < shape[0] and not visited[ny, nx]:
                maze[(y + ny) // 2, (x + nx) // 2] = 0
                maze[ny, nx] = 0
                visited[ny, nx] = True
                stack.append((nx, ny))
                maze_coords.append((nx, ny))
                found = True
                break
        if not found:
            stack.pop()

    maze = cv2.resize(maze, (400, 400), interpolation=cv2.INTER_NEAREST)
    maze = cv2.cvtColor(maze, cv2.COLOR_GRAY2BGR)
    cv2.circle(maze, (25, 25), 10, (0, 255, 0), -1)
    cv2.circle(maze, (375, 375), 10, (255, 0, 0), -1)
    return maze, maze_coords


def scale_maze_coordinates(maze_coords):
    return [(int(x * (400 / 11)), int(y * (400 / 11))) for x, y in maze_coords]


def is_gaze_on_path(point, scaled_maze, threshold=55):
    return any(np.linalg.norm(np.array(point) - np.array(coord)) < threshold for coord in scaled_maze)


def fail_session(session_status, reason, frame, maze_frame, ui_callback):
    session_status["authorized"] = False
    session_status["reason"] = reason
    ui_callback(frame, maze_frame, reason)


def authenticate_gaze(terminate_signal, maze_coords_ref, gaze_coords_ref, ui_callback, expected_face_encoding, session_status):
    """Track gaze while continuously checking that the same face remains present."""
    maze_coords_ref.clear()
    gaze_coords_ref.clear()
    session_status["authorized"] = True
    session_status["reason"] = ""

    webcam = None
    for backend in (cv2.CAP_DSHOW, cv2.CAP_ANY):
        candidate = cv2.VideoCapture(0, backend)
        if not candidate or not candidate.isOpened():
            if candidate:
                candidate.release()
            continue
        try:
            candidate.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            candidate.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        except cv2.error:
            pass
        webcam = candidate
        break

    if webcam is None:
        session_status["authorized"] = False
        session_status["reason"] = "Unable to open camera for gaze authentication."
        blank_maze, _ = create_connected_maze_with_display(size=5)
        ui_callback(np.zeros((720, 1280, 3), dtype=np.uint8), blank_maze, session_status["reason"])
        return

    maze_base, coords = create_connected_maze_with_display(size=5)
    maze_coords_ref.extend(coords)
    scaled_maze = scale_maze_coordinates(coords)

    frame_count = 0
    last_face_seen_at = time.monotonic()
    last_gaze_seen_at = time.monotonic()
    bad_gaze_count = 0

    try:
        while not terminate_signal():
            ret, frame = webcam.read()
            if not ret:
                continue

            now = time.monotonic()
            frame_count += 1
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            status_text = "Tracking authenticated user..."

            if frame_count % FACE_CHECK_INTERVAL == 0:
                face_locations = face_recognition.face_locations(rgb_frame)
                if len(face_locations) == 0:
                    status_text = "Face not detected. Stay in front of the camera."
                elif len(face_locations) > 1:
                    fail_session(
                        session_status,
                        "Another person appeared in frame. Session logged out.",
                        frame,
                        maze_base.copy(),
                        ui_callback,
                    )
                    break
                else:
                    encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                    if not encodings:
                        status_text = "Face could not be encoded. Please face the camera."
                    else:
                        distance = face_recognition.face_distance([expected_face_encoding], encodings[0])[0]
                        if distance > FACE_MATCH_THRESHOLD:
                            fail_session(
                                session_status,
                                "Face changed during gaze verification. Session logged out.",
                                frame,
                                maze_base.copy(),
                                ui_callback,
                            )
                            break
                        else:
                            last_face_seen_at = now

                if now - last_face_seen_at >= FACE_MISSING_TIMEOUT:
                    fail_session(
                        session_status,
                        "No authenticated face detected for too long. Session logged out.",
                        frame,
                        maze_base.copy(),
                        ui_callback,
                    )
                    break

            gaze.refresh(frame)
            annotated = frame.copy()

            left_pupil = gaze.pupil_left_coords()
            right_pupil = gaze.pupil_right_coords()

            for pupil in [left_pupil, right_pupil]:
                if pupil:
                    px, py = int(pupil[0]), int(pupil[1])
                    cv2.line(annotated, (px - 20, py), (px + 20, py), (0, 255, 0), 3)
                    cv2.line(annotated, (px, py - 20), (px, py + 20), (0, 255, 0), 3)

            temp_maze = maze_base.copy()
            if left_pupil:
                mx = int((left_pupil[0] / 1280) * 400)
                my = int((left_pupil[1] / 720) * 400)
                current_point = (mx, my)
                gaze_coords_ref.append(current_point)
                cv2.circle(temp_maze, (mx, my), 8, (255, 0, 0), -1)
                last_gaze_seen_at = now

                if is_gaze_on_path(current_point, scaled_maze):
                    bad_gaze_count = 0
                else:
                    bad_gaze_count += 1
                    status_text = "Incorrect gaze detected. Follow the maze path."
                    cv2.circle(temp_maze, current_point, 10, (0, 0, 255), 2)
                    if bad_gaze_count >= MAX_CONSECUTIVE_BAD_GAZE:
                        fail_session(
                            session_status,
                            "Incorrect gaze pattern detected. Session logged out.",
                            annotated,
                            temp_maze,
                            ui_callback,
                        )
                        break
            else:
                status_text = "Eyes not detected. Keep looking at the maze."

            if now - last_gaze_seen_at >= INACTIVITY_TIMEOUT:
                fail_session(
                    session_status,
                    "Gaze inactivity timeout reached. Session logged out.",
                    annotated,
                    temp_maze,
                    ui_callback,
                )
                break

            ui_callback(annotated, temp_maze, status_text)
    finally:
        webcam.release()


def compare_coordinates(maze_coords, gaze_coords):
    """Match recent gaze points against the maze path."""
    if not gaze_coords:
        return False

    scaled_maze = []
    for x, y in maze_coords:
        scaled_maze.append((int(x * (400 / 11)), int(y * (400 / 11))))

    threshold, matches = 60, 0
    for g in gaze_coords[-100:]:
        for m in scaled_maze:
            if np.linalg.norm(np.array(g) - np.array(m)) < threshold:
                matches += 1
                break
    return matches >= 5
