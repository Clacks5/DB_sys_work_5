import io
import numpy as np
import mysql.connector
import pyglet.window.key as key

from one import (
    ovw, ossop, osso, ouc,
    khi_rs007l, or_2fg7
)


DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "041512",
    "database": "db_sys_work_5",
}


def blob_to_ndarray(blob):
    return np.load(io.BytesIO(blob))


def interpolate_joint_path(start_qs, goal_qs, n_steps=80):
    start_qs = np.asarray(start_qs, dtype=np.float64)
    goal_qs = np.asarray(goal_qs, dtype=np.float64)

    return [
        (1.0 - t) * start_qs + t * goal_qs
        for t in np.linspace(0.0, 1.0, n_steps)
    ]


def load_success_candidates():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            pgik.placement_grasp_ik_id,
            pgik.placement_id,
            pgik.grasp_id,
            pgik.goal_joint_values,
            pgik.pre_grasp_world_pos,
            pgik.pre_grasp_world_rotmat,
            p.world_pos,
            p.world_rotmat
        FROM placement_grasp_ik AS pgik
        JOIN placement AS p
            ON pgik.placement_id = p.placement_id
        WHERE pgik.ik_success = 1
        ORDER BY pgik.placement_grasp_ik_id
        """
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    candidates = []

    for row in rows:
        (
            pgik_id,
            placement_id,
            grasp_id,
            goal_qs_blob,
            pre_pos_blob,
            pre_rot_blob,
            bunny_pos_blob,
            bunny_rot_blob,
        ) = row

        candidates.append(
            {
                "pgik_id": pgik_id,
                "placement_id": placement_id,
                "grasp_id": grasp_id,
                "goal_qs": blob_to_ndarray(goal_qs_blob),
                "pre_pos": blob_to_ndarray(pre_pos_blob),
                "pre_rot": blob_to_ndarray(pre_rot_blob),
                "bunny_pos": blob_to_ndarray(bunny_pos_blob),
                "bunny_rot": blob_to_ndarray(bunny_rot_blob),
            }
        )

    return candidates


def main():
    candidates = load_success_candidates()

    if not candidates:
        raise RuntimeError("IK成功候補がありません")

    base = ovw.World(
        cam_pos=(2, 2, 1.5),
        cam_lookat_pos=(0, 0, 0.5),
        toggle_auto_cam_orbit=False,
    )

    ossop.frame().attach_to(base.scene)

    ground = ossop.plane(pos=(0, 0, 0.01))
    ground.attach_to(base.scene)

    bunny = osso.SceneObject.from_file(
        "bunny.stl",
        collision_type=ouc.CollisionType.MESH,
    )
    bunny.rgb = (0.8, 0.7, 0.6)
    bunny.attach_to(base.scene)

    robot = khi_rs007l.RS007L()
    robot.attach_to(base.scene)

    gripper = or_2fg7.OR2FG7()
    gripper.attach_to(base.scene)
    robot.engage(gripper)

    home_qs = robot.qs.copy()

    index = {"value": 0}
    anim = {
        "path": [],
        "cursor": 0,
        "playing": False,
    }

    prev = {
        "left": False,
        "right": False,
        "space": False,
    }

    def apply_candidate():
        c = candidates[index["value"]]

        bunny.pos = c["bunny_pos"]
        bunny.rotmat = c["bunny_rot"]

        path = interpolate_joint_path(
            home_qs,
            c["goal_qs"],
            n_steps=80,
        )

        anim["path"] = path
        anim["cursor"] = 0
        anim["playing"] = False

        robot.fk(qs=home_qs)

        print(
            f"candidate {index['value'] + 1}/{len(candidates)} | "
            f"pgik_id={c['pgik_id']} | "
            f"placement_id={c['placement_id']} | "
            f"grasp_id={c['grasp_id']}"
        )

    def tick(dt):
        left = base.input_manager.is_key_pressed(key.LEFT)
        right = base.input_manager.is_key_pressed(key.RIGHT)
        space = base.input_manager.is_key_pressed(key.SPACE)

        if right and not prev["right"]:
            index["value"] = (index["value"] + 1) % len(candidates)
            apply_candidate()

        if left and not prev["left"]:
            index["value"] = (index["value"] - 1) % len(candidates)
            apply_candidate()

        if space and not prev["space"]:
            anim["playing"] = True
            anim["cursor"] = 0

        if anim["playing"] and anim["path"]:
            qs = anim["path"][anim["cursor"]]
            robot.fk(qs=qs)

            anim["cursor"] += 1
            if anim["cursor"] >= len(anim["path"]):
                anim["playing"] = False

        prev["left"] = left
        prev["right"] = right
        prev["space"] = space

    apply_candidate()

    print("操作: ← → で候補切替, Spaceでプレビュー再生")

    base.schedule_interval(tick, interval=0.005)
    base.run()


if __name__ == "__main__":
    main()