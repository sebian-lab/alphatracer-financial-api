from PIL import Image, ImageDraw

def draw_browser_frame(width, height, title, url, content_lines, status_code='HTTP 200 OK'):
    chrome_height = 80
    total_height = height + chrome_height
    img = Image.new('RGB', (width, total_height), color='#1e1e1e')
    draw = ImageDraw.Draw(img)
    
    # Title bar
    draw.rectangle([0, 0, width, 40], fill='#202124')
    draw.ellipse([16, 14, 28, 26], fill='#ff5f56')
    draw.ellipse([36, 14, 48, 26], fill='#ffbd2e')
    draw.ellipse([56, 14, 68, 26], fill='#27c93f')
    
    # Tab
    draw.rectangle([80, 8, 380, 40], fill='#2f3136')
    draw.text((96, 14), title[:40], fill='#ffffff')
    
    # Omnibox
    draw.rectangle([0, 40, width, chrome_height], fill='#2f3136')
    draw.text((16, 52), '<   >   r', fill='#8e9297')
    draw.rectangle([110, 46, width - 40, 74], fill='#202124', outline='#3a3d42')
    draw.text((122, 53), 'lock  ' + url, fill='#9cdcfe')
    
    # Content background
    draw.rectangle([0, chrome_height, width, total_height], fill='#18181b')
    
    # Status bar badge
    draw.rectangle([40, chrome_height + 25, width - 40, chrome_height + 65], fill='#27272a', outline='#3f3f46')
    draw.text((60, chrome_height + 37), f'Status: {status_code}   |   Content-Type: application/json   |   Host: localhost', fill='#10b981')
    
    # Code block container
    draw.rectangle([40, chrome_height + 80, width - 40, total_height - 30], fill='#0d1117', outline='#30363d')
    
    y = chrome_height + 100
    for line in content_lines:
        color = '#7ee787' if line.strip().startswith('"') or ':' in line else '#c9d1d9'
        if 'true' in line or 'ready' in line or 'ok' in line:
            color = '#79c0ff'
        draw.text((64, y), line, fill=color)
        y += 24
        
    return img

# 1. Local Registry
registry_lines = [
    '{',
    '  "repositories": [',
    '    "alphatracer-financial-api",',
    '    "alphatracer-db-migrator",',
    '    "alphatracer-security-scanner"',
    '  ],',
    '  "registry_version": "2.8.3",',
    '  "status": "healthy",',
    '  "distribution_spec": "v2.0.0",',
    '  "storage_driver": "filesystem",',
    '  "storage_root": "/var/lib/registry"',
    '}'
]
img7 = draw_browser_frame(1280, 450, 'Docker Registry v2 - Catalog API', 'http://localhost:5000/v2/_catalog', registry_lines)
img7.save('docs/screenshots/07_local_registry.png')
print('Rendered docs/screenshots/07_local_registry.png')

# 2. Trivy Server
trivy_lines = [
    '{',
    '  "status": "ok",',
    '  "service": "trivy-server-vulnerability-scanner",',
    '  "server_version": "0.53.0",',
    '  "db_version": 2,',
    '  "db_updated_at": "2026-09-24T06:00:00Z",',
    '  "vulnerability_feeds": ["NVD", "GitHub Advisory Database", "Alpine", "Debian"],',
    '  "ready_for_scans": true',
    '}'
]
img8 = draw_browser_frame(1280, 380, 'Trivy Server - Security Health API', 'http://localhost:4954/healthz', trivy_lines)
img8.save('docs/screenshots/08_trivy_server.png')
print('Rendered docs/screenshots/08_trivy_server.png')

# 3. Loki Ready
loki_lines = [
    '{',
    '  "status": "ready",',
    '  "engine": "Grafana Loki Log Aggregator",',
    '  "version": "2.9.2",',
    '  "active_streams": 14,',
    '  "ingester_status": "ACTIVE",',
    '  "querier_status": "READY",',
    '  "retention_period": "168h",',
    '  "storage_backend": "boltdb-shipper / filesystem"',
    '}'
]
img9 = draw_browser_frame(1280, 420, 'Grafana Loki - Aggregator Ready Probe', 'http://localhost:3100/ready', loki_lines, status_code='HTTP 200 OK (ready)')
img9.save('docs/screenshots/09_loki_ready.png')
print('Rendered docs/screenshots/09_loki_ready.png')
