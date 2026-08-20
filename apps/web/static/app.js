// Khởi tạo bản đồ — tự động dùng Mapbox style nếu server có token
let map;
let activeMarkers = [];
let lastPlanPayload = null;
let simSessionId = null;
let simPollTimer = null;
let vehicleMarker = null;

async function initApp() {
    // Lấy config từ API (mapbox token, chế độ station)
    let mapboxToken = '';
    let hasRealStations = false;
    try {
        const cfg = await fetch('/config').then(r => r.json());
        mapboxToken = cfg.mapbox_token || '';
        hasRealStations = cfg.has_real_stations || false;
    } catch (_) {}

    // Chọn style bản đồ
    const mapStyle = mapboxToken
        ? `https://api.mapbox.com/styles/v1/mapbox/dark-v11/tiles/256/{z}/{x}/{y}@2x?access_token=${mapboxToken}`
        : 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

    // Mapbox tile style cần dùng rasterDemSource, MapLibre GL dùng dạng object style
    const styleConfig = mapboxToken
        ? {
            version: 8,
            sources: {
                'mapbox-tiles': {
                    type: 'raster',
                    tiles: [`https://api.mapbox.com/styles/v1/mapbox/dark-v11/tiles/{z}/{x}/{y}?access_token=${mapboxToken}`],
                    tileSize: 256,
                    attribution: '© Mapbox © OpenStreetMap'
                }
            },
            layers: [{ id: 'background', type: 'raster', source: 'mapbox-tiles' }]
        }
        : 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

    map = new maplibregl.Map({
        container: 'map',
        style: styleConfig,
        center: [105.8542, 21.0285], // Hà Nội
        zoom: 6,
    });

    // Hiển thị badge chế độ
    showModeBadge(hasRealStations);

    // Gắn event listener sau khi map sẵn sàng
    setupFormListener();
}

function showModeBadge(hasRealStations) {
    const badge = document.createElement('div');
    badge.style.cssText = `
        position: fixed; top: 16px; right: 16px; z-index: 1000;
        background: ${hasRealStations ? 'rgba(0, 200, 100, 0.2)' : 'rgba(255, 165, 0, 0.2)'};
        border: 1px solid ${hasRealStations ? '#00c864' : '#ffa500'};
        color: ${hasRealStations ? '#00c864' : '#ffa500'};
        padding: 6px 14px; border-radius: 20px; font-size: 0.8rem;
        font-family: var(--font-body, sans-serif); backdrop-filter: blur(8px);
    `;
    badge.innerText = hasRealStations ? '⚡ Trạm sạc thực tế (OCM)' : '🔮 Chế độ Demo';
    document.body.appendChild(badge);
}

function setupFormListener() {
// Lắng nghe form submit
document.getElementById('plan-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const btn = e.target.querySelector('button');
    const originalText = btn.innerText;
    btn.innerText = 'Đang tính toán...';
    btn.style.opacity = '0.7';
    btn.disabled = true;

    try {
        const originStr = document.getElementById('origin').value.split(',');
        const destStr = document.getElementById('destination').value.split(',');
        const vehicleId = document.getElementById('vehicle').value;
        const startSoc = parseFloat(document.getElementById('soc').value);

        const payload = {
            origin: { lat: parseFloat(originStr[0]), lon: parseFloat(originStr[1]) },
            destination: { lat: parseFloat(destStr[0]), lon: parseFloat(destStr[1]) },
            vehicle_id: vehicleId,
            start_soc_pct: startSoc
        };

        // FIX: Gọi đúng endpoint /api/plan
        const response = await fetch('/api/plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`Lỗi API (${response.status}): ${errText}`);
        }

        const data = await response.json();

        // Cập nhật số liệu
        document.getElementById('res-time').innerText = formatTime(data.total_duration_minutes);
        document.getElementById('res-drive').innerText = formatTime(data.total_drive_minutes);
        document.getElementById('res-charge').innerText = formatTime(data.total_charge_minutes);
        document.getElementById('res-energy').innerText = `${data.total_energy_kwh.toFixed(1)} kWh`;

        const warningsBox = document.getElementById('warnings');
        if (data.warnings && data.warnings.length > 0) {
            warningsBox.innerHTML = data.warnings.map(w => `⚠️ ${w}`).join('<br/>');
            warningsBox.classList.remove('hidden');
        } else {
            warningsBox.classList.add('hidden');
        }

        document.getElementById('results').classList.remove('hidden');

        renderStopsList(data.stops || []);

        // Vẽ bản đồ — chỉ các trạm thực sự nằm trong kế hoạch tối ưu (data.stops),
        // không vẽ toàn bộ trạm tìm được trên bản đồ để tránh gây nhiễu.
        drawRoute(payload.origin, payload.destination, data.stops || [], data.route_waypoints || []);

        // Lưu payload để dùng cho nút "Bắt đầu mô phỏng"
        lastPlanPayload = payload;
        stopSimulation(); // huỷ phiên mô phỏng cũ (nếu có) khi lập kế hoạch mới
        document.getElementById('sim-start-btn').classList.remove('hidden');
        document.getElementById('sim-panel').classList.add('hidden');

    } catch (err) {
        alert('Lỗi tính toán: ' + err.message);
    } finally {
        btn.innerText = originalText;
        btn.style.opacity = '1';
        btn.disabled = false;
    }
}); // end addEventListener
} // end setupFormListener

// ---------------------------------------------------------------------------
// Mô phỏng xe chạy live: demo cho "dữ liệu xe trực tiếp" — gọi backend
// /api/simulate/*, poll trạng thái mỗi giây, vẽ marker xe di chuyển trên bản
// đồ và hiển thị SOC/cảnh báo/lập-lại-kế-hoạch theo thời gian thực.
// ---------------------------------------------------------------------------

const SIM_POLL_MS = 1000;
const STATUS_LABELS = {
    planning: 'Đang lập kế hoạch…',
    driving: '🚗 Đang lái xe',
    charging: '⚡ Đang sạc',
    arrived: '🏁 Đã đến nơi',
    failed: '❌ Thất bại',
};

async function startSimulation() {
    if (!lastPlanPayload) return;
    const btn = document.getElementById('sim-start-btn');
    btn.disabled = true;
    btn.innerText = 'Đang khởi động…';

    try {
        const resp = await fetch('/api/simulate/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(lastPlanPayload),
        });
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        simSessionId = data.session_id;

        const c = data.conditions;
        document.getElementById('sim-conditions').innerText =
            `Điều kiện thực tế chuyến này: tải phụ ${c.extra_load_kg.toFixed(0)}kg, ` +
            `${c.temperature_c.toFixed(0)}°C, gió ${c.wind_mps >= 0 ? '+' : ''}${c.wind_mps.toFixed(1)}m/s`;

        document.getElementById('sim-panel').classList.remove('hidden');
        btn.classList.add('hidden');

        simPollTimer = setInterval(pollSimulation, SIM_POLL_MS);
        pollSimulation();
    } catch (err) {
        alert('Không khởi động được mô phỏng: ' + err.message);
        btn.disabled = false;
        btn.innerText = '🚗 Bắt đầu mô phỏng xe chạy live';
    }
}

async function pollSimulation() {
    if (!simSessionId) return;
    let data;
    try {
        const resp = await fetch(`/api/simulate/${simSessionId}`);
        if (!resp.ok) throw new Error('session not found');
        data = await resp.json();
    } catch (_) {
        stopSimulation();
        return;
    }

    const badge = document.getElementById('sim-status-badge');
    badge.innerText = STATUS_LABELS[data.status] || data.status;
    badge.className = `sim-badge status-${data.status}`;

    document.getElementById('sim-soc').innerText = `${data.soc_pct.toFixed(0)}%`;
    document.getElementById('sim-soc-fill').style.width = `${Math.max(0, Math.min(100, data.soc_pct))}%`;

    const warnBox = document.getElementById('sim-warnings');
    warnBox.innerHTML = data.warnings.map(w => `<div class="sim-warning-item">${w}</div>`).join('');

    // Cập nhật vị trí xe live trên bản đồ
    if (!vehicleMarker) {
        const el = document.createElement('div');
        el.innerHTML = '🚗';
        el.style.cssText = 'font-size: 26px; filter: drop-shadow(0 0 10px rgba(0,240,255,1));';
        vehicleMarker = new maplibregl.Marker({ element: el }).setLngLat([data.lon, data.lat]).addTo(map);
    } else {
        vehicleMarker.setLngLat([data.lon, data.lat]);
    }

    // Nếu kế hoạch bị lập lại giữa chừng, cập nhật lại danh sách trạm
    renderStopsList(data.stops || []);

    if (data.status === 'arrived' || data.status === 'failed') {
        clearInterval(simPollTimer);
        simPollTimer = null;
        if (data.status === 'failed' && data.error) {
            warnBox.innerHTML += `<div class="sim-warning-item">❌ ${data.error}</div>`;
        }
    }
}

function stopSimulation() {
    if (simPollTimer) clearInterval(simPollTimer);
    simPollTimer = null;
    if (simSessionId) {
        fetch(`/api/simulate/${simSessionId}/stop`, { method: 'POST' }).catch(() => {});
    }
    simSessionId = null;
    if (vehicleMarker) {
        vehicleMarker.remove();
        vehicleMarker = null;
    }
    const btn = document.getElementById('sim-start-btn');
    btn.disabled = false;
    btn.innerText = '🚗 Bắt đầu mô phỏng xe chạy live';
}

document.getElementById('sim-start-btn').addEventListener('click', startSimulation);
document.getElementById('sim-stop-btn').addEventListener('click', () => {
    stopSimulation();
    document.getElementById('sim-panel').classList.add('hidden');
    document.getElementById('sim-start-btn').classList.remove('hidden');
});

// Khởi động ứng dụng
initApp();

function formatTime(minutes) {
    if (minutes < 60) return `${Math.round(minutes)}m`;
    const h = Math.floor(minutes / 60);
    const m = Math.round(minutes % 60);
    return `${h}h ${m}m`;
}

function clearMap() {
    // Xoá markers cũ
    activeMarkers.forEach(m => m.remove());
    activeMarkers = [];
    // Xoá layer và source cũ
    if (map.getLayer('route')) map.removeLayer('route');
    if (map.getSource('route')) map.removeSource('route');
}

function renderStopsList(stops) {
    const container = document.getElementById('stops-list');
    if (!stops || stops.length === 0) {
        container.innerHTML = '<div class="stop-card">✅ Không cần dừng — pin đủ đi thẳng tới đích.</div>';
        return;
    }
    container.innerHTML = stops.map(s => `
        <div class="stop-card ${s.is_rest_stop ? 'rest-stop' : ''}">
            <div class="stop-title">
                <span>${s.is_rest_stop ? '🛌' : '⚡'} Chặng ${s.order} — ${s.operator || 'Trạm sạc'}</span>
            </div>
            <div>Đến nơi còn <span class="stop-soc">${s.arrival_soc_pct.toFixed(0)}%</span> →
                 Sạc <b>${Math.round(s.charge_minutes)} phút</b> đến
                 <span class="stop-soc">${s.departure_soc_pct.toFixed(0)}%</span> rồi đi tiếp</div>
            <div class="stop-reason">${s.reason || ''}</div>
        </div>
    `).join('');
}

function drawRoute(origin, dest, stops, routeWaypoints) {
    clearMap();

    // Dùng waypoints từ API (theo QL1A) nếu có, nếu không dùng đường thẳng
    const coordinates = (routeWaypoints && routeWaypoints.length > 0)
        ? routeWaypoints
        : [
            [origin.lon, origin.lat],
            ...stops.map(s => [s.lon, s.lat]),
            [dest.lon, dest.lat]
          ];

    map.addSource('route', {
        type: 'geojson',
        data: {
            type: 'Feature',
            properties: {},
            geometry: { type: 'LineString', coordinates }
        }
    });

    map.addLayer({
        id: 'route',
        type: 'line',
        source: 'route',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: {
            'line-color': '#00f0ff',
            'line-width': 4,
            'line-opacity': 0.85,
            'line-dasharray': [1, 0]
        }
    });

    // Thả marker cho Origin
    addMarker(origin.lat, origin.lon, '🚗', 'Điểm đi');

    // Thả marker cho từng trạm sạc trong kế hoạch tối ưu
    stops.forEach(stop => {
        const label = `⚡ Chặng ${stop.order} — ${stop.operator || ''}\n` +
            `Đến: ${stop.arrival_soc_pct.toFixed(0)}% → Sạc ${Math.round(stop.charge_minutes)}p → Đi: ${stop.departure_soc_pct.toFixed(0)}%\n` +
            `${stop.reason || ''}`;
        addMarker(stop.lat, stop.lon, stop.is_rest_stop ? '🛌' : '⚡', label);
    });

    // Thả marker cho Destination
    addMarker(dest.lat, dest.lon, '🏁', 'Điểm đến');

    // Fit bounds
    const allLngLats = coordinates.map(c => new maplibregl.LngLat(c[0], c[1]));
    const bounds = allLngLats.reduce((b, ll) => b.extend(ll), new maplibregl.LngLatBounds(allLngLats[0], allLngLats[0]));
    map.fitBounds(bounds, { padding: { top: 60, bottom: 60, left: 460, right: 60 }, maxZoom: 10 });
}

function addMarker(lat, lon, emoji, label) {
    const el = document.createElement('div');
    el.className = 'map-marker';
    el.innerHTML = emoji;
    el.style.cssText = `
        font-size: 24px;
        cursor: pointer;
        filter: drop-shadow(0 0 8px rgba(0,240,255,0.8));
    `;

    const popup = new maplibregl.Popup({ offset: 25, closeButton: false })
        .setText(label);

    const marker = new maplibregl.Marker({ element: el })
        .setLngLat([lon, lat])
        .setPopup(popup)
        .addTo(map);

    activeMarkers.push(marker);
}
