USE db_sys_work_5;

-- =========================
-- object
-- =========================

CREATE TABLE object (
    object_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    mesh_path VARCHAR(255)
);

-- =========================
-- stable_pose
-- =========================

CREATE TABLE stable_pose (
    stable_pose_id INT AUTO_INCREMENT PRIMARY KEY,

    object_id INT NOT NULL,

    pos LONGBLOB NOT NULL,
    rotmat LONGBLOB NOT NULL,

    seg_id INT,
    stability_score DOUBLE,

    CONSTRAINT fk_stablepose_object
        FOREIGN KEY (object_id)
        REFERENCES object(object_id)
);

-- =========================
-- translation_xy
-- =========================

CREATE TABLE translation_xy (
    xy_id INT AUTO_INCREMENT PRIMARY KEY,
    x DOUBLE NOT NULL,
    y DOUBLE NOT NULL,
    UNIQUE (x, y)
);

-- =========================
-- yaw_angle
-- =========================

CREATE TABLE yaw_angle (
    yaw_id INT AUTO_INCREMENT PRIMARY KEY,
    yaw_deg DOUBLE NOT NULL UNIQUE
);

-- =========================
-- placement
-- =========================

CREATE TABLE placement (
    placement_id INT AUTO_INCREMENT PRIMARY KEY,

    stable_pose_id INT NOT NULL,
    xy_id INT NOT NULL,
    yaw_id INT NOT NULL,

    world_pos LONGBLOB NOT NULL,
    world_rotmat LONGBLOB NOT NULL,

    CONSTRAINT fk_placement_stablepose
        FOREIGN KEY (stable_pose_id)
        REFERENCES stable_pose(stable_pose_id),

    CONSTRAINT fk_placement_xy
        FOREIGN KEY (xy_id)
        REFERENCES translation_xy(xy_id),

    CONSTRAINT fk_placement_yaw
        FOREIGN KEY (yaw_id)
        REFERENCES yaw_angle(yaw_id),

    UNIQUE (stable_pose_id, xy_id, yaw_id)
);

-- =========================
-- grasp
-- =========================

CREATE TABLE grasp (
    grasp_id INT AUTO_INCREMENT PRIMARY KEY,

    object_id INT NOT NULL,
    stable_pose_id INT NOT NULL,

    grasp_pose_obj LONGBLOB NOT NULL,
    pre_grasp_pose_obj LONGBLOB NOT NULL,

    jaw_width DOUBLE NOT NULL,
    score DOUBLE,

    CONSTRAINT fk_grasp_object
        FOREIGN KEY (object_id)
        REFERENCES object(object_id),

    CONSTRAINT fk_grasp_stablepose
        FOREIGN KEY (stable_pose_id)
        REFERENCES stable_pose(stable_pose_id)
);

-- =========================
-- placement_grasp_ik
-- =========================

CREATE TABLE placement_grasp_ik (
    placement_grasp_ik_id INT AUTO_INCREMENT PRIMARY KEY,

    placement_id INT NOT NULL,
    grasp_id INT NOT NULL,

    ik_success BOOLEAN NOT NULL,
    state_valid BOOLEAN NOT NULL,

    goal_joint_values LONGBLOB,

    pre_grasp_world_pos LONGBLOB,
    pre_grasp_world_rotmat LONGBLOB,

    CONSTRAINT fk_pgik_placement
        FOREIGN KEY (placement_id)
        REFERENCES placement(placement_id),

    CONSTRAINT fk_pgik_grasp
        FOREIGN KEY (grasp_id)
        REFERENCES grasp(grasp_id),

    UNIQUE (placement_id, grasp_id)
);