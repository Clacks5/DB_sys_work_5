import io
import numpy as np
import mysql.connector

import one.geom.fitting as ogf
import one.geom.surface as ogs
import one.grasp.placement as ogp
from one import ouc, osso


DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "041512",
    "database": "db_sys_work_5",
}


def ndarray_to_blob(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, arr)
    return buf.getvalue()


def main():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    # object_id取得
    cur.execute("SELECT object_id FROM object WHERE name = %s", ("bunny",))
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("object tableに bunny がありません")

    object_id = row[0]

    # bunny読み込み
    bunny = osso.SceneObject.from_file(
        "bunny.stl",
        collision_type=ouc.CollisionType.MESH,
    )

    geom = bunny.collisions[0].geom
    geom_hull = ogf.convex_hull(geom)
    facets = ogs.segment_surface(geom_hull)

    stable_poses = ogp.compute_stable_poses(
        geom_hull.vs,
        geom_hull.fs,
        facets,
        com=None,
        stable_thresh=10.0,
    )

    print(f"Found {len(stable_poses)} stable poses")

    for pos, rotmat, seg_id, ratio, _ in stable_poses:
        cur.execute(
            """
            INSERT INTO stable_pose (
                object_id,
                pos,
                rotmat,
                seg_id,
                stability_score
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                object_id,
                ndarray_to_blob(np.asarray(pos, dtype=np.float64)),
                ndarray_to_blob(np.asarray(rotmat, dtype=np.float64)),
                int(seg_id),
                float(ratio),
            ),
        )

    conn.commit()
    cur.close()
    conn.close()

    print("stable_pose table updated")


if __name__ == "__main__":
    main()