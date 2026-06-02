import random
import pickle
import cv2
import numpy as np
import pyglet

from one import (
    ovw, ossop, osso, ouc,
    khi_rs007l, or_2fg7,
)
from paths import BUNNY_MESH_PATH

def main():
    # 1. 共有されたPickleファイルからデータを読み込む (DB接続不要！)
    try:
        with open("portable_paths.pkl", "rb") as f:
            candidates = pickle.load(f)
    except FileNotFoundError:
        print("エラー: 'portable_paths.pkl' が見つかりません。")
        return

    # ランダムに1つ選ぶ
    c = random.choice(candidates)

    # 2. ビューアとロボットのセットアップ
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
    bunny.pos = c["bunny_pos"]
    bunny.rotmat = c["bunny_rot"]
    bunny.attach_to(base.scene)

    robot = khi_rs007l.RS007L()
    robot.attach_to(base.scene)
    gripper = or_2fg7.OR2FG7()
    gripper.attach_to(base.scene)
    robot.engage(gripper)

    path = c["path_qs"]
    robot.fk(qs=path[0])

    print(f"[REC] pgik_id={c['pgik_id']} の自動録画を開始します...")

    # アニメーション・録画用の状態管理
    state = {
        "cursor": 0,
        "writer": None,
        "filename": f"auto_record_pgik_{c['pgik_id']}.mp4"
    }

    def tick(dt):
        # ロボットを動かす
        if state["cursor"] < len(path):
            robot.fk(qs=path[state["cursor"]])
            
            # 画面キャプチャと録画
            color_buffer = pyglet.image.get_buffer_manager().get_color_buffer()
            image_data = color_buffer.get_image_data()
            data = image_data.get_data('RGB', color_buffer.width * 3)
            arr = np.frombuffer(data, dtype=np.uint8).reshape((color_buffer.height, color_buffer.width, 3))
            arr = np.flipud(arr)
            frame = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

            if state["writer"] is None:
                h, w = frame.shape[:2]
                # mp4vでエラーが出る場合は 'XVID' にして .avi に変更してください
                fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
                state["writer"] = cv2.VideoWriter(state["filename"], fourcc, 50.0, (w, h))

            state["writer"].write(frame)
            state["cursor"] += 1

        else:
            # 最後まで動いたら録画を終了してウィンドウを閉じる
            if state["writer"] is not None:
                state["writer"].release()
            print(f"[REC] 録画完了！ '{state['filename']}' を保存しました。")
            pyglet.app.exit() # ウィンドウを自動で閉じる

    base.schedule_interval(tick, interval=0.02)
    base.run()

if __name__ == "__main__":
    main()