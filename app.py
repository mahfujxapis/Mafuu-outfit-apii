from flask import Flask, request, jsonify, send_file
import requests
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import os

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=10)
session = requests.Session()

# --- Configuration ---
API_KEY = "MAFU"
BACKGROUND_FILENAME = "outfit.jpg"  # Ensure your image file name matches this 
IMAGE_TIMEOUT = 8
CANVAS_SIZE = (800, 800)

def fetch_player_info(uid: str):
    if not uid:
        return None
    player_info_url = f"https://info-strikerxyash.vercel.app/player-info?uid={uid}"
    try:
        resp = session.get(player_info_url, timeout=IMAGE_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None

def fetch_and_process_image(image_url: str, size: tuple = (165, 165)):
    try:
        resp = session.get(image_url, timeout=IMAGE_TIMEOUT)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        return img.resize(size, Image.LANCZOS)
    except Exception:
        return None

@app.route('/outfit-image', methods=['GET'])
def outfit_image():
    uid = request.args.get('uid')
    key = request.args.get('key')

    if key != API_KEY:
        return jsonify({'error': 'Invalid or missing API key'}), 401
    if not uid:
        return jsonify({'error': 'Missing uid parameter'}), 400

    player_data = fetch_player_info(uid)
    if not player_data:
        return jsonify({'error': 'Failed to fetch player info'}), 500

    outfit_ids = player_data.get("AccountProfileInfo", {}).get("EquippedOutfit", []) or []
    
    # Matching the 8 spots on your background image 
    required_starts = ["211", "214", "212", "203", "204", "205", "208", "211"]
    fallback_ids = ["211000000", "214000000", "212000000", "203000000", "204000000", "205000000", "208000000", "211000001"]

    def get_img(idx, code):
        matched = next((str(o) for o in outfit_ids if str(o).startswith(code)), fallback_ids[idx])
        return fetch_and_process_image(f'https://iconapi.wasmer.app/{matched}')

    futures = [executor.submit(get_img, i, c) for i, c in enumerate(required_starts)]

    try:
        bg_path = os.path.join(os.path.dirname(__file__), BACKGROUND_FILENAME)
        background = Image.open(bg_path).convert("RGBA").resize(CANVAS_SIZE, Image.LANCZOS)
    except:
        return jsonify({'error': f'Background image {BACKGROUND_FILENAME} not found!'}), 500

    canvas = Image.new("RGBA", CANVAS_SIZE)
    canvas.paste(background, (0, 0))

    # Real positions for the 8-circle background 
    positions = [
        (318, 38), (540, 128), (635, 345), (540, 565),
        (318, 658), (95, 565), (5, 345), (95, 128)
    ]

    for idx, future in enumerate(futures):
        img = future.result()
        if img:
            canvas.paste(img, positions[idx], img)

    output = BytesIO()
    canvas.save(output, format='PNG')
    output.seek(0)
    return send_file(output, mimetype='image/png')

if __name__ == '__main__':
    # Required for Render to detect the correct port
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
