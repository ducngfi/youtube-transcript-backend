from flask import Flask, request, jsonify, Response
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
from flask_cors import CORS
import re
import logging
import json
import os

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

logging.basicConfig(level=logging.DEBUG)

def extract_video_id(url):
    # This regex pattern matches various forms of YouTube URLs
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(?:embed\/)?(?:v\/)?(?:shorts\/)?(?:live\/)?(?:embed\/)?(?:shorts\/)?(?:v=)?(\S{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def format_transcript(transcript, format_type='txt'):
    if format_type == 'txt':
        return '\n'.join([f"{item['text']}" for item in transcript])
    elif format_type == 'srt':
        srt = ''
        for i, item in enumerate(transcript, 1):
            start = format_time(item['start'])
            end = format_time(item['start'] + item['duration'])
            srt += f"{i}\n{start} --> {end}\n{item['text']}\n\n"
        return srt
    elif format_type == 'json':
        return json.dumps(transcript, indent=2)
    else:
        return json.dumps(transcript)

def format_time(seconds):
    hours = int(seconds / 3600)
    minutes = int((seconds % 3600) / 60)
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace('.', ',')

@app.route('/api/transcript', methods=['GET'])
def get_transcript():
    app.logger.info(f"Received request: {request.url}")
    video_url = request.args.get('video_url')
    format_type = request.args.get('format', 'json')
    app.logger.info(f"Video URL: {video_url}, Format: {format_type}")
    
    if not video_url:
        app.logger.error("No video URL provided")
        return jsonify({"error": "No video URL provided"}), 400
    
    video_id = extract_video_id(video_url)
    if not video_id:
        app.logger.error(f"Invalid YouTube URL: {video_url}")
        return jsonify({"error": "Invalid YouTube URL"}), 400
    
    try:
        app.logger.info(f"Fetching transcript for video ID: {video_id}")
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        app.logger.info("Transcript fetched successfully")
        
        formatted_transcript = format_transcript(transcript, format_type)
        
        if format_type == 'txt':
            return Response(formatted_transcript, mimetype='text/plain')
        elif format_type == 'srt':
            return Response(formatted_transcript, mimetype='text/plain')
        else:
            return Response(formatted_transcript, mimetype='application/json')
    except NoTranscriptFound:
        app.logger.error("No transcript found for the video")
        return jsonify({"error": "No transcript found for this video", "details": "The video does not have any available transcripts."}), 404
    except TranscriptsDisabled:
        app.logger.error("Transcripts are disabled for this video")
        return jsonify({"error": "Transcripts are disabled for this video", "details": "The video owner has disabled transcripts for this content."}), 403
    except VideoUnavailable:
        app.logger.error("The video is unavailable")
        return jsonify({"error": "The video is unavailable", "details": "The requested video could not be accessed. It might be private or deleted."}), 404
    except Exception as e:
        app.logger.error(f"Error fetching transcript: {str(e)}")
        app.logger.error(f"Error type: {type(e).__name__}")
        app.logger.error(f"Error args: {e.args}")
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({"message": "Backend is working"}), 200

@app.route('/api/test-transcript/<video_id>', methods=['GET'])
def test_transcript(video_id):
    app.logger.debug(f"Attempting to fetch transcript for video ID: {video_id}")
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        app.logger.info(f"Successfully fetched transcript for video ID: {video_id}")
        return jsonify({"success": True, "transcript": transcript[:5]})
    except Exception as e:
        app.logger.error(f"Error fetching transcript for video ID {video_id}: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/check-transcript', methods=['GET'])
def check_transcript():
    video_url = request.args.get('video_url')
    if not video_url:
        return jsonify({"error": "No video URL provided"}), 400
    
    video_id = extract_video_id(video_url)
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL"}), 400
    
    try:
        YouTubeTranscriptApi.list_transcripts(video_id)
        return jsonify({"available": True, "message": "Transcript is available"}), 200
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable):
        return jsonify({"available": False, "message": "Transcript is not available for this video"}), 200
    except Exception as e:
        app.logger.error(f"Error checking transcript availability: {str(e)}")
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
