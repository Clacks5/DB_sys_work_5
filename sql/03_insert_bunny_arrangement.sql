USE db_sys_work_5;

INSERT IGNORE INTO translation_xy (x, y) VALUES
    (-0.20, -0.20),
    (-0.20,  0.20),
    ( 0.20, -0.20),
    ( 0.20,  0.20);

INSERT IGNORE INTO yaw_angle (yaw_deg) VALUES
    (0),
    (90),
    (180),
    (270);