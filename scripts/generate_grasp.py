import io
from datetime import datetime

import numpy as np
import mysql.connector

from one import ouc, osso, or_2fg7, oum
import one.grasp.antipodal as og_antipodal

from db_config import DB_CONFIG
from paths import BUNNY_MESH_PATH


GRASP_PARAMS = {
    "density": 0.01,
    "normal_tol_deg": 20,
    "roll_step_deg": 30,
    "max_grasps": 80,
}


def log(message: str):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def ndarray_to_blob(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, arr)
    return buf.getvalue()


def blob_to_ndarray(blob: bytes) -> np.ndarray:
    return np.load(io.BytesIO(blob))


def collect_grasps(gripper, bunny):
    results = []
    checked_count = 0

    for pose, pre_pose, jaw_width, score, collided in og_antipodal.antipodal_iter(
        gripper=gripper,
        tgt_sobj=bunny,
        density=GRASP_PARAMS["density"],
        normal_tol_deg=GRASP_PARAMS["normal_tol_deg"],
        roll_step_deg=GRASP_PARAMS["roll_step_deg"],
    ):
        checked_count += 1

        if not collided:
            results.append((pose, pre_pose, jaw_width, float(score)))
            log(
                "accepted grasp "
                f"{len(results)}/{GRASP_PARAMS['max_grasps']} "
                f"(checked={checked_count}, jaw_width={jaw_width:.4f}, score={score:.4f})"
            )

        if checked_count == 1 or checked_count % 20 == 0:
            log(f"checked grasp candidates: {checked_count}, accepted: {len(results)}")

        if len(results) >= GRASP_PARAMS["max_grasps"]:
            break

    log(f"checked grasp candidates total: {checked_count}")
    return results


def compute_grasps(gripper, bunny):
    try:
        log("trying GPU collision checker")
        grasps = collect_grasps(gripper, bunny)
        log("GPU collision checker finished")
        return grasps
    except Exception as exc:
        log(f"GPU collision checker failed: {repr(exc)}")
        log("retrying with CPU collision checker")

        original_gpu_module = og_antipodal.ocgcb
        try:
            og_antipodal.ocgcb = og_antipodal.occs
            grasps = collect_grasps(gripper, bunny)
            log("CPU collision checker finished")
            return grasps
        finally:
            og_antipodal.ocgcb = original_gpu_module


def main():
    log("connecting to database")
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    log("loading bunny object id")
    cur.execute("SELECT object_id FROM object WHERE name = %s", ("bunny",))
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("object tableに bunny がありません")
    object_id = row[0]
    log(f"object_id={object_id}")

    log("loading first stable pose")
    cur.execute(
        """
        SELECT stable_pose_id, pos, rotmat
        FROM stable_pose
        ORDER BY stable_pose_id
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("stable_pose table が空です")

    stable_pose_id, pos_blob, rot_blob = row
    stable_pos = blob_to_ndarray(pos_blob)
    stable_rotmat = blob_to_ndarray(rot_blob)
    log(f"stable_pose_id={stable_pose_id}")

    log(f"loading mesh: {BUNNY_MESH_PATH}")
    bunny = osso.SceneObject.from_file(
        str(BUNNY_MESH_PATH),
        collision_type=ouc.CollisionType.MESH,
    )

    bunny.pos = stable_pos
    bunny.rotmat = stable_rotmat

    gripper = or_2fg7.OR2FG7()

    log("computing antipodal grasps")
    grasps = compute_grasps(gripper, bunny)
    log(f"found grasps: {len(grasps)}")

    tf_bunny = oum.tf_from_rotmat_pos(stable_rotmat, stable_pos)
    tf_bunny_inv = np.linalg.inv(tf_bunny)

    count = 0
    log("inserting grasps into database")

    for pose_world, pre_pose_world, jaw_width, score in grasps:
        # bunny配置に対する相対姿勢として保存
        grasp_pose_obj = tf_bunny_inv @ pose_world
        pre_grasp_pose_obj = tf_bunny_inv @ pre_pose_world

        cur.execute(
            """
            INSERT INTO grasp (
                object_id,
                stable_pose_id,
                grasp_pose_obj,
                pre_grasp_pose_obj,
                jaw_width,
                score
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                object_id,
                stable_pose_id,
                ndarray_to_blob(np.asarray(grasp_pose_obj, dtype=np.float64)),
                ndarray_to_blob(np.asarray(pre_grasp_pose_obj, dtype=np.float64)),
                float(jaw_width),
                float(score),
            ),
        )

        count += 1
        if count == 1 or count % 10 == 0 or count == len(grasps):
            log(f"inserted grasps: {count}/{len(grasps)}")

    conn.commit()
    log("database commit completed")

    cur.close()
    conn.close()

    log(f"inserted grasps total: {count}")


if __name__ == "__main__":
    main()