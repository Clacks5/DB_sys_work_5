import io
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime

import numpy as np
import mysql.connector

from one import (
    oum, ouc, osso, ossop,
    ocm, khi_rs007l, or_2fg7
)

from db_config import DB_CONFIG
from paths import BUNNY_MESH_PATH


def log(message: str):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def ndarray_to_blob(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, arr)
    return buf.getvalue()


def blob_to_ndarray(blob: bytes) -> np.ndarray:
    return np.load(io.BytesIO(blob))

def ik_tcp_nearest_quiet(robot, tgt_rotmat, tgt_pos):
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        return robot.ik_tcp_nearest(
            tgt_rotmat=tgt_rotmat,
            tgt_pos=tgt_pos,
        )

def load_placements(cur):
    cur.execute(
        """
        SELECT placement_id, world_pos, world_rotmat
        FROM placement
        ORDER BY placement_id
        """
    )
    return cur.fetchall()


def load_grasps(cur):
    cur.execute(
        """
        SELECT grasp_id, pre_grasp_pose_obj, jaw_width
        FROM grasp
        ORDER BY grasp_id
        """
    )
    return cur.fetchall()


def main():
    log("connecting to database")
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    log("initializing robot and gripper")
    robot = khi_rs007l.RS007L()
    gripper = or_2fg7.OR2FG7()
    robot.engage(gripper)

    log(f"loading mesh: {BUNNY_MESH_PATH}")
    bunny = osso.SceneObject.from_file(
        str(BUNNY_MESH_PATH),
        collision_type=ouc.CollisionType.MESH,
    )

    log("compiling MuJoCo collider")
    ground = ossop.plane(pos=(0, 0, 0.01))

    mjc = ocm.MJCollider()
    mjc.append(robot)
    mjc.append(gripper)
    mjc.append(bunny)
    mjc.append(ground)
    mjc.actors = [robot]
    mjc.compile(margin=0.0)

    placements = load_placements(cur)
    grasps = load_grasps(cur)
    total = len(placements) * len(grasps)

    log(f"placements: {len(placements)}")
    log(f"grasps: {len(grasps)}")
    log(f"total placement/grasp pairs: {total}")

    success_count = 0
    fail_count = 0
    processed_count = 0

    for p_i, (placement_id, world_pos_blob, world_rot_blob) in enumerate(placements, start=1):
        world_pos = blob_to_ndarray(world_pos_blob)
        world_rotmat = blob_to_ndarray(world_rot_blob)

        bunny.pos = world_pos
        bunny.rotmat = world_rotmat

        tf_bunny = oum.tf_from_rotmat_pos(world_rotmat, world_pos)
        placement_success = 0
        placement_fail = 0

        log(f"placement {p_i}/{len(placements)} started (placement_id={placement_id})")

        for g_i, (grasp_id, pre_grasp_blob, jaw_width) in enumerate(grasps, start=1):
            pre_grasp_obj = blob_to_ndarray(pre_grasp_blob)
            pre_grasp_world = tf_bunny @ pre_grasp_obj

            pre_pos = pre_grasp_world[:3, 3]
            pre_rotmat = pre_grasp_world[:3, :3]

            qs = ik_tcp_nearest_quiet(
                robot,
                tgt_rotmat=pre_rotmat,
                tgt_pos=pre_pos,
            )

            if qs is None:
                ik_success = 0
                state_valid = 0
                goal_blob = None
                fail_count += 1
                placement_fail += 1
            else:
                ik_success = 1

                mjc.set_mecba_qpos(
                    gripper,
                    (float(jaw_width) / 2, float(jaw_width) / 2),
                )

                robot.fk(qs=qs)
                gripper.fk(qs=(float(jaw_width) / 2, float(jaw_width) / 2))

                # 簡易的にはIKが解けたらvalid扱いでもOK
                # 衝突判定まで見る場合は、ここを必要に応じて調整
                state_valid = 1
                goal_blob = ndarray_to_blob(np.asarray(qs, dtype=np.float64))
                success_count += 1
                placement_success += 1

            cur.execute(
                """
                INSERT INTO placement_grasp_ik (
                    placement_id,
                    grasp_id,
                    ik_success,
                    state_valid,
                    goal_joint_values,
                    pre_grasp_world_pos,
                    pre_grasp_world_rotmat
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    ik_success = VALUES(ik_success),
                    state_valid = VALUES(state_valid),
                    goal_joint_values = VALUES(goal_joint_values),
                    pre_grasp_world_pos = VALUES(pre_grasp_world_pos),
                    pre_grasp_world_rotmat = VALUES(pre_grasp_world_rotmat)
                """,
                (
                    placement_id,
                    grasp_id,
                    ik_success,
                    state_valid,
                    goal_blob,
                    ndarray_to_blob(np.asarray(pre_pos, dtype=np.float64)),
                    ndarray_to_blob(np.asarray(pre_rotmat, dtype=np.float64)),
                ),
            )

            processed_count += 1
            if g_i == 1 or g_i % 20 == 0 or g_i == len(grasps):
                log(
                    f"placement {p_i}/{len(placements)} progress: "
                    f"grasp {g_i}/{len(grasps)}, "
                    f"placement_success={placement_success}, placement_failed={placement_fail}, "
                    f"total={processed_count}/{total}"
                )

        conn.commit()
        log(
            f"placement {p_i}/{len(placements)} committed: "
            f"success={placement_success}, failed={placement_fail}"
        )

    cur.close()
    conn.close()

    log(f"IK success total: {success_count}")
    log(f"IK failed total: {fail_count}")


if __name__ == "__main__":
    main()