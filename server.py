import base64
import os
import flask
from flask import request, jsonify
from flask import render_template
from flask_cors import CORS
from time import time
import controller
from PIL import Image
from openai import OpenAI
import dotenv
import json
import flask_limiter
from threading import Thread
import time as sleep_time
from flask_limiter.util import get_remote_address

dotenv.load_dotenv()

client = OpenAI(
    api_key=os.getenv("OAI_KEY"),
    base_url="https://jamsapi.hackclub.dev/openai",
)

app = flask.Flask(__name__)
CORS(app)
limiter = flask_limiter.Limiter(
    key_func=get_remote_address,
    app=app,
    strategy="fixed-window",
)

HEIGHT = 64
WIDTH = 64
RATELIMIT = 1  # How often do we let one user set a pixel (in seonds)
SAVE_INTERVAL = 60  # save state every 60 seconds, or any reasonable value
STATE_FILE = "canvas_state.json"

state = []  # The canvas state in memory is a 2D array of RGB stuff


@app.errorhandler(429)
def ratelimit_error(e):
    time_left = round(limiter.current_limit.reset_at - time(), 1)
    return (
        jsonify(
            {
                "success": False,
                "message": f"Rate limit exceeded. Try again in {time_left} seconds.",
                "try_in": time_left,
            }
        ),
        429,
    )


def hcLogo():
    newState = controller.send_image_to_esp32(
        "/home/pi/hackclub.jpg"
    )  # Configurable path
    for y in range(HEIGHT):
        for x in range(WIDTH):
            state[y][x] = newState[y][x]


def load_state():
    """Load the state from a file if it exists."""
    global state
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as file:
            state = json.load(file)
        for y in range(HEIGHT):
            for x in range(WIDTH):
                controller.set_pixel_color(x, y, *state[y][x])
    else:
        state = [[[0, 0, 0] for _ in range(WIDTH)] for _ in range(HEIGHT)]
        hcLogo()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                controller.set_pixel_color(x, y, *state[y][x])


def save_state():
    """Save the state to a file periodically."""
    while True:
        with open(STATE_FILE, "w") as file:
            json.dump(state, file)
        sleep_time.sleep(SAVE_INTERVAL)


# Load the state on startup
load_state()


def classify_and_clear_canvas(path: str = "/tmp/canvas.png") -> str:
    with open(path, "rb") as image_file:
        base64_screenshot = base64.b64encode(image_file.read()).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """Does this image contain anything offensive or inappropriate? Respond in JSON, e.g. {"offensive": false, "found": "nothing"}""",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_screenshot}"
                        },
                    },
                ],
            }
        ],
        max_tokens=40,
    )
    content = response.choices[0].message.content

    if json.loads(content)["offensive"]:
        controller.clear_canvas()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                state[y][x] = [0, 0, 0]

        return f"""Canvas cleared due to offensive content; found '{json.loads(content)["found"]}'"""
    else:
        return "No offensive content found"


@limiter.limit("1/minute")
@app.route("/report")
def report():
    img = Image.new("RGB", (WIDTH * 4, HEIGHT * 4))

    for y in range(HEIGHT):
        for x in range(WIDTH):
            for dy in range(4):
                for dx in range(4):
                    img.putpixel((x * 4 + dx, y * 4 + dy), tuple(state[y][x]))

    img.save("/tmp/canvas.png")

    status = classify_and_clear_canvas()

    return status


@app.route("/set_pixel_color", methods=["POST"])
@limiter.limit("1 per 1 seconds")
def set_pixel_color():
    data = request.json
    x = data["x"]
    y = data["y"]
    r = data["r"]
    g = data["g"]
    b = data["b"]

    if x < 0 or x >= WIDTH or y < 0 or y >= HEIGHT:
        return jsonify({"success": False, "error": "Invalid coordinates"})
    if r < 0 or r > 255 or g < 0 or g > 255 or b < 0 or b > 255:
        return jsonify({"success": False, "error": "Invalid color"})

    controller.set_pixel_color(x, y, r, g, b)
    state[y][x] = [r, g, b]
    print(x, y, r, g, b)
    return jsonify({"success": True})


@app.route("/get_state", methods=["GET"])
def get_state():
    return jsonify(state)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


if __name__ == "__main__":
    Thread(target=save_state, daemon=True).start()
    app.run(host="0.0.0.0", port=8732, debug=False)
