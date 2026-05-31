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


def blob_to_ndarray(blob: bytes) -> np.ndarray:
    return np.load(io.BytesIO(blob))


def load_all_placements():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            p.placement_id,
            p.world_pos,
            p.world_rotmat,
            sp.stable_pose_id,
            t.x,
            t.y,
            y.yaw_deg
        FROM placement AS p
        JOIN stable_pose AS sp
            ON p.stable_pose_id = sp.stable_pose_id
        JOIN translation_xy AS t
            ON p.xy_id = t.xy_id
        JOIN yaw_angle AS y
            ON p.yaw_id = y.yaw_id
        ORDER BY p.placement_id
        """
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    placements = []

    for (
        placement_id,
        pos_blob,
        rot_blob,
        stable_pose_id,
        x,
        y,
        yaw_deg,
    ) in rows:
        placements.append(
            {
                "placement_id": placement_id,
                "pos": blob_to_ndarray(pos_blob),
                "rotmat": blob_to_ndarray(rot_blob),
                "stable_pose_id": stable_pose_id,
                "x": x,
                "y": y,
                "yaw_deg": yaw_deg,
            }
        )

    return placements


def main():
    placements = load_all_placements()

    if not placements:
        raise RuntimeError("placement table is empty")

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

    def apply_placement():
        p = placements[index["value"]]

        bunny.pos = p["pos"]
        bunny.rotmat = p["rotmat"]

        print(
            f"placement {index['value'] + 1}/{len(placements)} | "
            f"id={p['placement_id']} | "
            f"stable_pose_id={p['stable_pose_id']} | "
            f"x={p['x']:.3f}, y={p['y']:.3f}, yaw={p['yaw_deg']:.1f}"
        )

    def tick(dt):
        left_pressed = base.input_manager.is_key_pressed(key.LEFT)
        right_pressed = base.input_manager.is_key_pressed(key.RIGHT)

        if right_pressed and not prev_key_state["right"]:
            index["value"] = (index["value"] + 1) % len(placements)
            apply_placement()

        if left_pressed and not prev_key_state["left"]:
            index["value"] = (index["value"] - 1) % len(placements)
            apply_placement()

        prev_key_state["left"] = left_pressed
        prev_key_state["right"] = right_pressed

    apply_placement()

    base.schedule_interval(tick, interval=0.05)
    base.run()


if __name__ == "__main__":
    main()