import io
import pickle
import numpy as np
import mysql.connector
from db_config import DB_CONFIG

def blob_to_ndarray(blob):
    return np.load(io.BytesIO(blob))

def main():
    print("データベースから経路データを抽出しています...")
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            pgik.placement_grasp_ik_id,
            pgik.path_joint_values,
            p.world_pos,
            p.world_rotmat
        FROM placement_grasp_ik AS pgik
        JOIN placement AS p ON pgik.placement_id = p.placement_id
        WHERE pgik.path_joint_values IS NOT NULL
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        print("経路データがありません。")
        return

    # データを扱いやすい辞書のリストに変換
    export_data = []
    for row in rows:
        export_data.append({
            "pgik_id": row[0],
            "path_qs": blob_to_ndarray(row[1]),
            "bunny_pos": blob_to_ndarray(row[2]),
            "bunny_rot": blob_to_ndarray(row[3]),
        })

    # Pickleファイルとして保存（Pythonで超高速に読み込める形式）
    with open("portable_paths.pkl", "wb") as f:
        pickle.dump(export_data, f)
        
    print(f"完了！ {len(export_data)}件のデータを 'portable_paths.pkl' に書き出しました。")
    print("他のメンバーには、このスクリプトと 'portable_paths.pkl' を渡せばOKです！")

if __name__ == "__main__":
    main()