import io
import cv2  # 追加: 動画保存用
import numpy as np
import mysql.connector
import pyglet.window.key as key
import pyglet  # 追加: 画面キャプチャ用

from one import (
    ovw, ossop, osso, ouc,
    khi_rs007l, or_2fg7,
)

from db_config import DB_CONFIG
from paths import BUNNY_MESH_PATH

def blob_to_ndarray(blob):
    return np.load(io.BytesIO(blob))

def load_random_path_candidate():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            pgik.placement_grasp_ik_id,
            pgik.placement_id,
            pgik.grasp_id,
            pgik.path_joint_values,
            p.world_pos,
            p.world_rotmat
        FROM placement_grasp_ik AS pgik
        JOIN placement AS p ON pgik.placement_id = p.placement_id
        WHERE pgik.path_joint_values IS NOT NULL
        ORDER BY RAND()
        LIMIT 1
        """
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row is None:
        return None

    return {
        "pgik_id": row[0],
        "placement_id": row[1],
        "grasp_id": row[2],
        "path_qs": blob_to_ndarray(row[3]),
        "bunny_pos": blob_to_ndarray(row[4]),
        "bunny_rot": blob_to_ndarray(row[5]),
    }

def main():
    base = ovw.World(
        cam_pos=(2.0, 2.0, 1.5),
        cam_lookat_pos=(0, 0, 0.5),
        toggle_auto_cam_orbit=False,
    )

    ossop.frame().attach_to(base.scene)
    ground = ossop.plane(pos=(0, 0, 0))
    ground.attach_to(base.scene)

    bunny = osso.SceneObject.from_file(
        str(BUNNY_MESH_PATH),
        collision_type=ouc.CollisionType.MESH,
    )
    bunny.attach_to(base.scene)

    robot = khi_rs007l.RS007L()
    robot.attach_to(base.scene)

    gripper = or_2fg7.OR2FG7()
    gripper.attach_to(base.scene)
    robot.engage(gripper)

    home_qs = robot.qs.copy()

    state = {
        "path": [],
        "cursor": 0,
        "waiting": False,
        "wait_time": 0.0,
    }

    # 録画用の状態管理
    record_state = {
        "is_recording": False,
        "writer": None,
        "count": 1,
        "prev_r_key": False
    }

    def select_next():
        c = load_random_path_candidate()
        if c is None:
            print("経路データが見つかりません。")
            return

        bunny.pos = c["bunny_pos"]
        bunny.rotmat = c["bunny_rot"]
        state["path"] = c["path_qs"]
        state["cursor"] = 0
        state["waiting"] = False
        state["wait_time"] = 0.0

        robot.fk(home_qs)
        print(f"pgik={c['pgik_id']} placement={c['placement_id']} grasp={c['grasp_id']}")

    select_next()

    print("\n--- 操作方法 ---")
    print("[R]キー : 録画の開始 / 終了 (カレントディレクトリにMP4が保存されます)")
    print("----------------\n")

    def tick(dt):
        # 1. 録画の開始・停止切り替えロジック
        r_key_pressed = base.input_manager.is_key_pressed(key.R)
        if r_key_pressed and not record_state["prev_r_key"]:
            record_state["is_recording"] = not record_state["is_recording"]
            
            if record_state["is_recording"]:
                print("[REC] 録画を開始しました...")
            else:
                if record_state["writer"] is not None:
                    record_state["writer"].release()
                    record_state["writer"] = None
                filename = f"simulation_record_{record_state['count']:03d}.mp4"
                print(f"[REC] 録画終了。 '{filename}' を保存しました！")
                record_state["count"] += 1
                
        record_state["prev_r_key"] = r_key_pressed

        # 2. ロボットのアニメーション進行
        if not state["waiting"]:
            if state["cursor"] < len(state["path"]):
                robot.fk(qs=state["path"][state["cursor"]])
                state["cursor"] += 1
            else:
                state["waiting"] = True
                state["wait_time"] = 0.0
        else:
            state["wait_time"] += dt
            if state["wait_time"] > 1.0:
                select_next()

        # 3. 録画中の場合、画面フレームを取得して書き込み
        if record_state["is_recording"]:
            try:
                # Pygletの画面バッファを取得
                color_buffer = pyglet.image.get_buffer_manager().get_color_buffer()
                image_data = color_buffer.get_image_data()
                data = image_data.get_data('RGB', color_buffer.width * 3)
                arr = np.frombuffer(data, dtype=np.uint8).reshape((color_buffer.height, color_buffer.width, 3))
                
                # Pyglet(左下原点)からOpenCV(左上原点)へ変換し、色もRGBからBGRへ
                arr = np.flipud(arr)
                frame = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

                # 初回書き込み時にVideoWriterを初期化
                if record_state["writer"] is None:
                    h, w = frame.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v') # MP4形式
                    filename = f"simulation_record_{record_state['count']:03d}.mp4"
                    # フレームレートはtickの間隔(0.02秒 = 50fps)に合わせる
                    record_state["writer"] = cv2.VideoWriter(filename, fourcc, 50.0, (w, h))

                record_state["writer"].write(frame)
            except Exception as e:
                print(f"[REC] 録画エラーが発生しました: {e}")
                record_state["is_recording"] = False

    base.schedule_interval(tick, interval=0.02)
    base.run()

if __name__ == "__main__":
    main()