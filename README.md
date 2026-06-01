# grasp_bunny

`grasp_bunny` は、`bunny.stl` に対するロボット把持候補を生成し、MySQL に保存して、3D ビューアで確認するための実験用リポジトリです。

大まかな処理の流れは次の通りです。

1. bunny メッシュを MySQL に登録する
2. bunny の安定姿勢を生成する
3. 安定姿勢、XY 平行移動、yaw 回転を組み合わせて配置候補を生成する
4. OnRobot 2FG7 グリッパで antipodal grasp 候補を生成する
5. Kawasaki RS007L ロボットで各「配置候補 x 把持候補」に対して IK を解く
6. IK に成功した候補を `one` のビューアで確認する

20260531時点のE-R図↓
[20260531_E-R図]("https://github.com/Clacks5/grasp_bunny/blob/main/E-R_diagram.png")

ロボット、把持、IK、可視化などの機能は外部ライブラリ [`wanweiwei07/one`](https://github.com/wanweiwei07/one) を使っています。このリポジトリは、その上に載せる SQL スキーマと実験スクリプトをまとめたものです。

## 必要なもの

- Python 3.12 以上
- MySQL server
- Git
- ビューアを使う場合は OpenGL が動く環境

Python パッケージ:

- `one` とその依存関係: `numpy`, `scipy`, `pyglet`, `mujoco`
- `mysql-connector-python`

## セットアップ

このリポジトリは `one` を Git submodule として使います。clone するときは submodule も一緒に取得してください。

```powershell
git clone --recurse-submodules https://github.com/Clacks5/grasp_bunny.git
cd grasp_bunny
```

submodule なしで clone した場合は、後から初期化できます。

```powershell
git submodule update --init --recursive
```

`one` の参照先は次のリポジトリです。

```text
https://github.com/wanweiwei07/one.git
```

仮想環境を作成します。

```bash
python -m venv .venv
```

仮想環境の有効化だけ OS によって異なります。

```powershell
# Windows / PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# Ubuntu / bash
source .venv/bin/activate
```

`one` と MySQL connector をインストールします。

```bash
pip install -e ./one
pip install mysql-connector-python
pip install matplotlib
```

## DB 接続設定

Python スクリプトは、MySQL の接続情報を環境変数から読みます。データベース名やユーザー名を変更していなければ、最低限パスワードだけをスクリプト実行前に同じターミナルで設定してください。

```powershell
# Windows / PowerShell
$env:GRASP_BUNNY_DB_PASSWORD = "your_password"
```

```bash
# Ubuntu / bash
export GRASP_BUNNY_DB_PASSWORD="your_password"
```

この設定は、そのターミナルを開いている間だけ有効です。

未設定の場合は、次の値が使われます。

```text
host     = localhost
user     = root
password = 空文字
database = grasp_bunny
```

## データベース作成

基本的には MySQL Workbench を使って SQL ファイルを実行します。

Workbench で MySQL サーバーに接続し、次の SQL ファイルを番号順に開いて実行してください。

```text
sql/00_create_db.sql
sql/01_create_table.sql
sql/02_insert_bunny_2_object.sql
sql/03_insert_bunny_arrangement.sql
```

Workbench では、各ファイルを開いて雷アイコン、または `Ctrl + Shift + Enter` でスクリプト全体を実行できます。

コマンドラインで実行する場合は、次のように実行します。

```powershell
mysql -u root -p < sql\00_create_db.sql
mysql -u root -p < sql\01_create_table.sql
mysql -u root -p < sql\02_insert_bunny_2_object.sql
mysql -u root -p < sql\03_insert_bunny_arrangement.sql
```

これにより、`grasp_bunny` データベース、必要なテーブル、bunny オブジェクト、配置パラメータが作成されます。

bunny メッシュは次の場所にあります。

```text
one/bunny.stl
```

SQL 側でも、同じパスが `object.mesh_path` に登録されます。

## データ生成

以下のスクリプトは、リポジトリのルートディレクトリから実行してください。生成中は進捗ログが表示されます。

安定姿勢を生成します。

```powershell
python scripts/generate_stable_pose.py
```

配置候補を生成します。

```powershell
python scripts/generate_placement.py
```

把持候補を生成します。

```powershell
python scripts/generate_grasp.py
```

各「配置候補 x 把持候補」に対して IK を確認します。

```powershell
python scripts/generate_placement_grasp_ik.py
```

最後のステップは、配置候補数と把持候補数の積だけ評価するため、少し時間がかかる場合があります。

## 確認とプレビュー

安定姿勢を確認します。

```powershell
python scripts/check_stable_pose.py
```

配置候補を確認します。

```powershell
python scripts/check_placement.py
```

把持候補を確認します。

```powershell
python scripts/check_grasp.py
```

IK に成功した操作候補を確認します。

```powershell
python scripts/preview_manipulation.py
```

IK に成功した候補をランダムに連続表示します。

```powershell
python scripts/preview_manipulation_random.py
```

ビューア操作:

- `Left` / `Right`: 候補を切り替え
- `Space`: 選択中の操作候補を再生

## ディレクトリ構成

```text
.
├── README.md
├── sql
│   ├── 00_create_db.sql
│   ├── 01_create_table.sql
│   ├── 02_insert_bunny_2_object.sql
│   └── 03_insert_bunny_arrangement.sql
├── scripts
│   ├── db_config.py
│   ├── paths.py
│   ├── generate_stable_pose.py
│   ├── generate_placement.py
│   ├── generate_grasp.py
│   ├── generate_placement_grasp_ik.py
│   ├── check_stable_pose.py
│   ├── check_placement.py
│   ├── check_grasp.py
│   ├── preview_manipulation.py
│   └── preview_manipulation_random.py
└── one
    └── 外部ライブラリ one と bunny メッシュ
```

## 注意

- `one` は外部ライブラリです。submodule を取得したあと、`python -m pip install -e ./one` でインストールしてください。
- DB パスワードはスクリプトに直接書かず、環境変数で管理してください。
- `generate_grasp.py` はまず GPU 衝突判定を使い、失敗した場合は CPU 衝突判定で再実行します。
- `generate_placement.py` と `generate_placement_grasp_ik.py` は UNIQUE 制約を使っているため、同じ組み合わせについては再実行しやすい作りになっています。
- `generate_stable_pose.py` と `generate_grasp.py` は生成結果を追記します。完全に作り直したい場合は、空のデータベースから SQL を実行し直してください。
