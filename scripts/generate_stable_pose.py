import io
from datetime import datetime

import numpy as np
import mysql.connector

import one.geom.fitting as ogf
import one.geom.surface as ogs
import one.grasp.placement as ogp
from one import ouc, osso

from db_config import DB_CONFIG
from paths import BUNNY_MESH_PATH


def log(message: str):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def ndarray_to_blob(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, arr)
    return buf.getvalue()


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

    log(f"loading mesh: {BUNNY_MESH_PATH}")
    bunny = osso.SceneObject.from_file(
        str(BUNNY_MESH_PATH),
        collision_type=ouc.CollisionType.MESH,
    )

    geom = bunny.collisions[0].geom
    log("computing convex hull")
    geom_hull = ogf.convex_hull(geom)

    log("segmenting hull surface")
    facets = ogs.segment_surface(geom_hull)
    log(f"surface facets: {len(facets)}")

    log("computing stable poses")
    stable_poses = ogp.compute_stable_poses(
        geom_hull.vs,
        geom_hull.fs,
        facets,
        com=None,
        stable_thresh=10.0,
    )

    log(f"found stable poses: {len(stable_poses)}")

    for i, (pos, rotmat, seg_id, ratio, _) in enumerate(stable_poses, start=1):
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
        log(f"inserted stable pose {i}/{len(stable_poses)} (seg_id={seg_id}, score={ratio:.4f})")

    conn.commit()
    log("database commit completed")

    cur.close()
    conn.close()

    log("stable_pose table updated")


if __name__ == "__main__":
    main()