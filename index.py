import os
import json
import io
import csv
import base64
import zlib
from flask import Flask, request, jsonify, render_template_string, send_file
from flask_cors import CORS

app = Flask(__name__)
# Enable CORS for all routes and all origins
CORS(app, resources={r"/*": {"origins": "*"}})

# Load student data
student_data = []
try:
    with open('students.json', 'r') as f:
        student_data = json.load(f)
except FileNotFoundError:
    # Create sample data if file doesn't exist
    import random
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    student_data = []
    for _ in range(100):
        name = ''.join(random.choice(chars) for _ in range(random.randint(5, 10)))
        marks = random.randint(0, 100)
        student_data.append({"name": name, "marks": marks})
    
    with open('students.json', 'w') as f:
        json.dump(student_data, f)

# Create a lookup dictionary
student_lookup = {student["name"]: student["marks"] for student in student_data}

@app.route('/')
def home():
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Student API</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #333; }
            .container { margin-top: 30px; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; }
            button { background: #4CAF50; color: white; padding: 10px 15px; border: none; cursor: pointer; }
            button:hover { background: #45a049; }
            pre { background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }
            .result { margin-top: 20px; }
            .url-display { margin-top: 20px; padding: 15px; background: #f4f4f4; border-radius: 5px; word-break: break-all; }
            .copy-btn { margin-top: 10px; }
        </style>
    </head>
    <body>
        <h1>Student API Demo</h1>
        
        <div class="container">
            <h2>Upload JSON File</h2>
            <form id="upload-form">
                <div class="form-group">
                    <label for="file">Select JSON file:</label>
                    <input type="file" id="file" accept=".json">
                </div>
                <button type="submit">Convert to CSV and Generate URL</button>
            </form>
            <div class="result" id="upload-result"></div>
        </div>

        <script>
            document.getElementById('upload-form').addEventListener('submit', async function(e) {
                e.preventDefault();
                const fileInput = document.getElementById('file');
                if (!fileInput.files.length) {
                    alert('Please select a file');
                    return;
                }

                const file = fileInput.files[0];
                const formData = new FormData();
                formData.append('file', file);

                try {
                    const response = await fetch('/upload', {
                        method: 'POST',
                        body: formData
                    });

                    if (response.ok) {
                        const data = await response.json();
                        const blobString = data.blob;
                        const fullUrl = `https://tds-vercel-ga-2-q-11.vercel.app/api/${blobString}/check`;
                        
                        const resultDiv = document.getElementById('upload-result');
                        resultDiv.innerHTML = `
                            <h3>API URL</h3>
                            <div class="url-display">${fullUrl}</div>
                            <button class="copy-btn" onclick="copyUrl()">Copy URL</button>
                        `;
                    } else {
                        alert('Upload failed: ' + await response.text());
                    }
                } catch (error) {
                    console.error('Error:', error);
                    alert('An error occurred');
                }
            });

            function copyUrl() {
                const urlText = document.querySelector('.url-display').textContent;
                navigator.clipboard.writeText(urlText).then(() => {
                    alert('URL copied to clipboard!');
                }).catch(err => {
                    console.error('Could not copy text: ', err);
                    // Fallback for older browsers
                    const tempInput = document.createElement('input');
                    tempInput.value = urlText;
                    document.body.appendChild(tempInput);
                    tempInput.select();
                    document.execCommand('copy');
                    document.body.removeChild(tempInput);
                    alert('URL copied to clipboard!');
                });
            }
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/api')
def api():
    # Get names from the query parameters
    names = request.args.getlist('name')
    
    if not names:
        return jsonify({"error": "No names provided"}), 400
    
    # Get marks for each name in the same order
    marks = [student_lookup.get(name, None) for name in names]
    
    # Return the marks in the exact format requested
    return jsonify({"marks": marks})

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
        
    try:
        # Load the JSON data
        data = json.load(file)
        
        # Convert to CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        if data and isinstance(data[0], dict):
            writer.writerow(data[0].keys())
        
        # Write rows
        for row in data:
            if isinstance(row, dict):
                writer.writerow(row.values())
        
        # Compress the CSV data
        csv_data = output.getvalue().encode('utf-8')
        compressed_data = zlib.compress(csv_data)
        
        # Convert to base64 for safe URL embedding
        blob_base64 = base64.urlsafe_b64encode(compressed_data).decode('utf-8')
        
        # Return the base64 string instead of a file
        return jsonify({"blob": blob_base64})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/<path:blob_id>/check', methods=['GET'])
def check_blob(blob_id):
    try:
        # Get names from the query parameters
        names = request.args.getlist('name')
        
        # In a real app, you might store and retrieve blobs from a database
        # For this demo, we'll assume the blob_id is the base64 encoded compressed data
        compressed_data = base64.urlsafe_b64decode(blob_id)
        decompressed_data = zlib.decompress(compressed_data).decode('utf-8')
        
        # Parse the CSV
        reader = csv.DictReader(io.StringIO(decompressed_data))
        parsed_data = list(reader)
        
        # If names were provided, filter the data
        if names:
            # Create a lookup dictionary from the parsed data
            data_lookup = {}
            for item in parsed_data:
                if 'name' in item:
                    data_lookup[item['name']] = item.get('marks')
                
            # Get the marks for the requested names
            requested_marks = [data_lookup.get(name) for name in names]
            # Convert marks to integers if possible
            requested_marks = [int(mark) if mark and mark.isdigit() else mark for mark in requested_marks]
            return jsonify({"marks": requested_marks})
        
        # If no names specified, return all data
        return jsonify({
            "success": True,
            "data": parsed_data,
            "count": len(parsed_data)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# Vercel handler
@app.route('/<path:path>')
def catch_all(path):
    return render_template_string('404 - Not Found')

# This is only used when running locally
if __name__ == '__main__':
    app.run(debug=True) 