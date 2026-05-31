import io
import random
import numpy as np
import mysql.connector

from one import (
    ovw,
    ossop,
    osso,
    ouc,
    khi_rs007l,
    or_2fg7,
)


DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "041512",
    "database": "db_sys_work_5",
}


def blob_to_ndarray(blob):
    return np.load(io.BytesIO(blob))


def interpolate_joint_path(start_qs, goal_qs, n_steps=25):
    start_qs = np.asarray(start_qs, dtype=np.float64)
    goal_qs = np.asarray(goal_qs, dtype=np.float64)

    return [
        (1.0 - t) * start_qs + t * goal_qs
        for t in np.linspace(0.0, 1.0, n_steps)
    ]


def load_random_candidate():

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            pgik.placement_grasp_ik_id,
            pgik.placement_id,
            pgik.grasp_id,
            pgik.goal_joint_values,

            p.world_pos,
            p.world_rotmat

        FROM placement_grasp_ik AS pgik

        JOIN placement AS p
            ON pgik.placement_id = p.placement_id

        WHERE pgik.ik_success = 1

        ORDER BY RAND()

        LIMIT 1
        """
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    if row is None:
        return None

    (
        pgik_id,
        placement_id,
        grasp_id,
        goal_blob,
        bunny_pos_blob,
        bunny_rot_blob,
    ) = row

    return {
        "pgik_id": pgik_id,
        "placement_id": placement_id,
        "grasp_id": grasp_id,
        "goal_qs": blob_to_ndarray(goal_blob),
        "bunny_pos": blob_to_ndarray(bunny_pos_blob),
        "bunny_rot": blob_to_ndarray(bunny_rot_blob),
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
        "bunny.stl",
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

    def select_next():

        c = load_random_candidate()

        if c is None:
            return

        bunny.pos = c["bunny_pos"]
        bunny.rotmat = c["bunny_rot"]

        state["path"] = interpolate_joint_path(
            home_qs,
            c["goal_qs"],
            n_steps=25,
        )

        state["cursor"] = 0
        state["waiting"] = False
        state["wait_time"] = 0.0

        robot.fk(home_qs)

        print(
            f"pgik={c['pgik_id']} "
            f"placement={c['placement_id']} "
            f"grasp={c['grasp_id']}"
        )

    select_next()

    def tick(dt):

        if not state["waiting"]:

            if state["cursor"] < len(state["path"]):

                robot.fk(
                    qs=state["path"][state["cursor"]]
                )

                state["cursor"] += 1

            else:

                state["waiting"] = True
                state["wait_time"] = 0.0

        else:

            state["wait_time"] += dt

            if state["wait_time"] > 1.0:

                select_next()

    base.schedule_interval(
        tick,
        interval=0.01,
    )

    base.run()


if __name__ == "__main__":
    main()