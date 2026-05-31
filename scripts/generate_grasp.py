import io
import numpy as np
import mysql.connector

from one import ouc, osso, or_2fg7, oum
import one.grasp.antipodal as og_antipodal

from db_config import DB_CONFIG
from paths import BUNNY_MESH_PATH


def ndarray_to_blob(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, arr)
    return buf.getvalue()


def blob_to_ndarray(blob: bytes) -> np.ndarray:
    return np.load(io.BytesIO(blob))


def compute_grasps(gripper, bunny):
    kwargs = {
        "gripper": gripper,
        "target_sobj": bunny,
        "density": 0.01,
        "normal_tol_deg": 20,
        "roll_step_deg": 30,
        "max_grasps": 80,
    }

    try:
        print("Trying GPU collision checker...")
        return og_antipodal.antipodal(**kwargs)
    except Exception as exc:
        print("GPU collision checker failed:", repr(exc))
        print("Retrying with CPU collision checker...")

        original_gpu_module = og_antipodal.ocgcb
        try:
            og_antipodal.ocgcb = og_antipodal.occs
            return og_antipodal.antipodal(**kwargs)
        finally:
            og_antipodal.ocgcb = original_gpu_module


def main():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("SELECT object_id FROM object WHERE name = %s", ("bunny",))
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("object tableに bunny がありません")
    object_id = row[0]

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

    bunny = osso.SceneObject.from_file(
        str(BUNNY_MESH_PATH),
        collision_type=ouc.CollisionType.MESH,
    )

    bunny.pos = stable_pos
    bunny.rotmat = stable_rotmat

    gripper = or_2fg7.OR2FG7()

    print("Computing antipodal grasps...")

    grasps = compute_grasps(gripper, bunny)

    print("Found grasps:", len(grasps))

    tf_bunny = oum.tf_from_rotmat_pos(stable_rotmat, stable_pos)
    tf_bunny_inv = np.linalg.inv(tf_bunny)

    count = 0

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

    conn.commit()

    cur.close()
    conn.close()

    print("Inserted grasps:", count)


if __name__ == "__main__":
    main()