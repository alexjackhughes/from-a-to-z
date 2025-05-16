import os
from pathlib import Path
import pandas as pd
from openai import OpenAI
import json
from PIL import Image
import base64
from io import BytesIO
from dotenv import load_dotenv

# Remove client initialization from module level
# client = OpenAI()

def encode_image_to_base64(image_path):
    """Convert image to base64 string."""
    with Image.open(image_path) as img:
        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        # Resize if too large (OpenAI has size limits)
        max_size = 1024
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = tuple(int(dim * ratio) for dim in img.size)
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        # Convert to base64
        buffered = BytesIO()
        img.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

def check_for_water(image_path, client):
    """Check if image contains lakes or rivers using OpenAI API."""
    try:
        # Encode image
        base64_image = encode_image_to_base64(image_path)

        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Does this image contain lakes or rivers? Return a JSON with format {\"status\": true|false}"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=300
        )

        # Parse response
        result = json.loads(response.choices[0].message.content)
        return result.get('status', False)

    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return False

def main():
    load_dotenv()
    # Initialize OpenAI client after loading environment variables
    client = OpenAI()

    # Directory containing the preview tiles
    preview_tiles_dir = Path("preview_tiles")

    # CSV file path
    csv_path = "water_detections.csv"

    # Create CSV file with headers if it doesn't exist
    if not os.path.exists(csv_path):
        pd.DataFrame(columns=['folder_name', 'image_name']).to_csv(csv_path, index=False)

    # Walk through all images
    for folder_path in preview_tiles_dir.iterdir():
        if not folder_path.is_dir():
            continue

        folder_name = folder_path.name
        print(f"Processing folder: {folder_name}")

        for image_path in folder_path.glob("*.jpg"):
            print(f"Checking image: {image_path.name}")

            # Check if image contains water
            has_water = check_for_water(image_path, client)

            if has_water:
                # Create DataFrame for single result
                result_df = pd.DataFrame([{
                    'folder_name': folder_name,
                    'image_name': image_path.name
                }])
                # Append to CSV
                result_df.to_csv(csv_path, mode='a', header=False, index=False)
                print(f"Found water in {image_path.name}")

    print("\nProcessing complete. Results are being written to CSV in real-time.")