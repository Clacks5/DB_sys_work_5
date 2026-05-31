import io
import numpy as np
import mysql.connector


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


def blob_to_ndarray(blob: bytes) -> np.ndarray:
    return np.load(io.BytesIO(blob))


def rotmat_z(deg: float) -> np.ndarray:
    th = np.deg2rad(deg)
    c = np.cos(th)
    s = np.sin(th)

    return np.array(
        [
            [c, -s, 0.0],
            [s,  c, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def main():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT stable_pose_id, pos, rotmat
        FROM stable_pose
        ORDER BY stable_pose_id
        """
    )
    stable_poses = cur.fetchall()

    cur.execute(
        """
        SELECT xy_id, x, y
        FROM translation_xy
        ORDER BY xy_id
        """
    )
    xy_rows = cur.fetchall()

    cur.execute(
        """
        SELECT yaw_id, yaw_deg
        FROM yaw_angle
        ORDER BY yaw_id
        """
    )
    yaw_rows = cur.fetchall()

    count = 0

    for stable_pose_id, pos_blob, rot_blob in stable_poses:
        stable_pos = blob_to_ndarray(pos_blob).astype(np.float64)
        stable_rotmat = blob_to_ndarray(rot_blob).astype(np.float64)

        for xy_id, x, y in xy_rows:
            for yaw_id, yaw_deg in yaw_rows:
                rz = rotmat_z(float(yaw_deg))

                world_pos = stable_pos.copy()
                world_pos[0] += float(x)
                world_pos[1] += float(y)

                world_rotmat = rz @ stable_rotmat

                cur.execute(
                    """
                    INSERT IGNORE INTO placement (
                        stable_pose_id,
                        xy_id,
                        yaw_id,
                        world_pos,
                        world_rotmat
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        stable_pose_id,
                        xy_id,
                        yaw_id,
                        ndarray_to_blob(world_pos),
                        ndarray_to_blob(world_rotmat),
                    ),
                )

                count += 1

    conn.commit()

    print("stable_pose count:", len(stable_poses))
    print("translation_xy count:", len(xy_rows))
    print("yaw_angle count:", len(yaw_rows))
    print("placement candidates:", count)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()