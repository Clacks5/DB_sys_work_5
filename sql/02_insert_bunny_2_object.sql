USE grasp_bunny;

INSERT INTO object(name, mesh_path)
VALUES('bunny', 'one/bunny.stl') AS new
ON DUPLICATE KEY UPDATE
    mesh_path = new.mesh_path;

SELECT * FROM object;
