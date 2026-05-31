import io
import numpy as np
import mysql.connector
import pyglet.window.key as key

from one import ovw, ossop, osso, ouc


DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "041512",
    "database": "db_sys_work_5",
}


def blob_to_ndarray(blob):
    return np.load(io.BytesIO(blob))


def load_all_stable_poses():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT stable_pose_id, pos, rotmat, seg_id, stability_score
        FROM stable_pose
        ORDER BY stable_pose_id
        """
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    poses = []
    for stable_pose_id, pos_blob, rot_blob, seg_id, score in rows:
        poses.append({
            "stable_pose_id": stable_pose_id,
            "pos": blob_to_ndarray(pos_blob),
            "rotmat": blob_to_ndarray(rot_blob),
            "seg_id": seg_id,
            "score": score,
        })

    return poses


def main():
    poses = load_all_stable_poses()

    if not poses:
        raise RuntimeError("stable_pose table is empty")

    base = ovw.World(
        cam_pos=(1.5, 1.5, 1.0),
        cam_lookat_pos=(0, 0, 0.2),
        toggle_auto_cam_orbit=False,
    )

    ossop.frame().attach_to(base.scene)

    plane = ossop.plane(pos=(0, 0, 0))
    plane.attach_to(base.scene)

    bunny = osso.SceneObject.from_file(
        "bunny.stl",
        collision_type=ouc.CollisionType.MESH,
    )
    bunny.rgb = (0.8, 0.7, 0.6)
    bunny.attach_to(base.scene)

    index = {"value": 0}
    prev_key_state = {
        "left": False,
        "right": False,
    }

    def apply_pose():
        p = poses[index["value"]]
        bunny.pos = p["pos"]
        bunny.rotmat = p["rotmat"]

        print(
            f"stable_pose {index['value'] + 1}/{len(poses)} | "
            f"id={p['stable_pose_id']} | "
            f"seg_id={p['seg_id']} | "
            f"score={p['score']}"
        )

    def tick(dt):
        left_pressed = base.input_manager.is_key_pressed(key.LEFT)
        right_pressed = base.input_manager.is_key_pressed(key.RIGHT)

        if right_pressed and not prev_key_state["right"]:
            index["value"] = (index["value"] + 1) % len(poses)
            apply_pose()

        if left_pressed and not prev_key_state["left"]:
            index["value"] = (index["value"] - 1) % len(poses)
            apply_pose()

        prev_key_state["left"] = left_pressed
        prev_key_state["right"] = right_pressed

    apply_pose()

    base.schedule_interval(tick, interval=0.05)
    base.run()


if __name__ == "__main__":
    main()