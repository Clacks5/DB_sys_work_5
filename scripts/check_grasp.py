import io
import numpy as np
import mysql.connector
import pyglet.window.key as key

from one import ovw, ossop, osso, ouc, or_2fg7


DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "041512",
    "database": "db_sys_work_5",
}


def blob_to_ndarray(blob):
    return np.load(io.BytesIO(blob))


def load_grasps():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            g.grasp_id,
            g.stable_pose_id,
            g.grasp_pose_obj,
            g.pre_grasp_pose_obj,
            g.jaw_width,
            g.score,
            sp.pos,
            sp.rotmat
        FROM grasp AS g
        JOIN stable_pose AS sp
            ON g.stable_pose_id = sp.stable_pose_id
        ORDER BY g.grasp_id
        """
    )

    rows = cur.fetchall()
    cur.close()
    conn.close()

    grasps = []
    for row in rows:
        (
            grasp_id,
            stable_pose_id,
            grasp_blob,
            pre_grasp_blob,
            jaw_width,
            score,
            stable_pos_blob,
            stable_rot_blob,
        ) = row

        stable_pos = blob_to_ndarray(stable_pos_blob)
        stable_rot = blob_to_ndarray(stable_rot_blob)

        grasp_obj = blob_to_ndarray(grasp_blob)
        pre_grasp_obj = blob_to_ndarray(pre_grasp_blob)

        tf_stable = np.eye(4)
        tf_stable[:3, :3] = stable_rot
        tf_stable[:3, 3] = stable_pos

        grasp_world = tf_stable @ grasp_obj
        pre_grasp_world = tf_stable @ pre_grasp_obj

        grasps.append(
            {
                "grasp_id": grasp_id,
                "stable_pose_id": stable_pose_id,
                "grasp_world": grasp_world,
                "pre_grasp_world": pre_grasp_world,
                "jaw_width": jaw_width,
                "score": score,
                "stable_pos": stable_pos,
                "stable_rot": stable_rot,
            }
        )

    return grasps


def main():
    grasps = load_grasps()

    if not grasps:
        raise RuntimeError("grasp table is empty")

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

    gripper = or_2fg7.OR2FG7()
    gripper.attach_to(base.scene)

    pre_gripper = or_2fg7.OR2FG7()
    pre_gripper.rgb = (0.0, 0.5, 1.0)
    pre_gripper.alpha = 0.3
    pre_gripper.attach_to(base.scene)

    index = {"value": 0}
    prev = {"left": False, "right": False}

    def apply_grasp():
        g = grasps[index["value"]]

        bunny.pos = g["stable_pos"]
        bunny.rotmat = g["stable_rot"]

        grasp_tf = g["grasp_world"]
        pre_tf = g["pre_grasp_world"]

        gripper.grip_at(
            grasp_tf[:3, 3],
            grasp_tf[:3, :3],
            float(g["jaw_width"]),
        )

        pre_gripper.grip_at(
            pre_tf[:3, 3],
            pre_tf[:3, :3],
            float(g["jaw_width"]),
        )

        print(
            f"grasp {index['value'] + 1}/{len(grasps)} | "
            f"id={g['grasp_id']} | "
            f"stable_pose_id={g['stable_pose_id']} | "
            f"jaw_width={g['jaw_width']:.4f} | "
            f"score={g['score']}"
        )

    def tick(dt):
        left = base.input_manager.is_key_pressed(key.LEFT)
        right = base.input_manager.is_key_pressed(key.RIGHT)

        if right and not prev["right"]:
            index["value"] = (index["value"] + 1) % len(grasps)
            apply_grasp()

        if left and not prev["left"]:
            index["value"] = (index["value"] - 1) % len(grasps)
            apply_grasp()

        prev["left"] = left
        prev["right"] = right

    apply_grasp()
    base.schedule_interval(tick, 0.05)
    base.run()


if __name__ == "__main__":
    main()