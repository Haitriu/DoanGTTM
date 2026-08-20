-- Bật extension PostGIS để hỗ trợ lưu tọa độ và truy vấn không gian
CREATE EXTENSION IF NOT EXISTS postgis;

-- Bảng lưu trữ Trạm Sạc
CREATE TABLE IF NOT EXISTS stations (
    id VARCHAR(128) PRIMARY KEY, -- ID từ nguồn bên ngoài (ví dụ OCM-123)
    name VARCHAR(255) NOT NULL,
    operator VARCHAR(255),
    -- geom là cột địa lý lưu theo chuẩn WGS 84 (SRID 4326)
    geom geometry(Point, 4326) NOT NULL,
    address TEXT,
    amenities JSONB, -- Các tiện ích như 'restroom', 'food'
    data_confidence VARCHAR(50), -- high, medium, low
    last_verified_at TIMESTAMP WITH TIME ZONE
);

-- Bảng Connector (1 trạm có nhiều Connector)
CREATE TABLE IF NOT EXISTS station_connectors (
    id SERIAL PRIMARY KEY,
    station_id VARCHAR(128) REFERENCES stations(id) ON DELETE CASCADE,
    connector_type VARCHAR(50) NOT NULL, -- e.g., 'ccs', 'type2'
    max_power_kw NUMERIC(10, 2) NOT NULL,
    count INT NOT NULL DEFAULT 1
);

-- Tạo Spatial Index để truy vấn "tìm trạm gần đây" nhanh siêu tốc
CREATE INDEX IF NOT EXISTS idx_stations_geom ON stations USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_station_connectors_station_id ON station_connectors(station_id);

-- Hàm helper để tìm trạm sạc xung quanh bán kính
CREATE OR REPLACE FUNCTION find_stations_nearby(
    lon FLOAT,
    lat FLOAT,
    radius_meters FLOAT
) RETURNS SETOF stations AS $$
BEGIN
    RETURN QUERY
    SELECT *
    FROM stations
    WHERE ST_DWithin(
        geom::geography,
        ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography,
        radius_meters
    );
END;
$$ LANGUAGE plpgsql;
