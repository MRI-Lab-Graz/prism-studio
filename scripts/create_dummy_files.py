#!/usr/bin/env python3
"""
Generate dummy test files for psycho-validator testing
"""

import os
import json
from PIL import Image
import numpy as np
import wave

def create_dummy_image(filepath, width=800, height=600):
    """Create a dummy image file"""
    # Create a random RGB image
    img_array = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(img_array)
    img.save(filepath)

def create_dummy_audio(filepath, duration=2.0, sample_rate=44100):
    """Create a dummy WAV audio file"""
    # Generate a simple sine wave
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    frequency = 440  # A4 note
    wave_data = np.sin(2 * np.pi * frequency * t)
    
    # Convert to 16-bit integers
    wave_data = (wave_data * 32767).astype(np.int16)
    
    with wave.open(filepath, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(wave_data.tobytes())

def create_sidecar_json(filepath, metadata):
    """Create a JSON sidecar file with metadata"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(metadata, f, indent=2)

def create_sidecar_json(filepath, metadata):
    """Create a JSON sidecar file with metadata"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(metadata, f, indent=2)

def main():
    # Create consistent test dataset (no errors, no warnings)
    print("Creating consistent_test_dataset...")
    
    # Create directories
    os.makedirs("consistent_test_dataset/sub-001/image", exist_ok=True)
    os.makedirs("consistent_test_dataset/sub-001/audio", exist_ok=True)
    os.makedirs("consistent_test_dataset/sub-002/image", exist_ok=True)
    os.makedirs("consistent_test_dataset/sub-002/audio", exist_ok=True)
    
    # Create inheritance file
    inheritance_metadata = {
        "Study": {
            "StudyID": "STUDY_2024_001",
            "TaskName": "recognition"
        },
        "Categories": {
            "StudyDomain": "cognitive"
        },
        "Metadata": {
            "SchemaVersion": "1.0.0",
            "Creator": "Psycho-Validator Demo Team",
            "CreationDate": "2024-01-15",
            "License": "CC-BY"
        }
    }
    create_sidecar_json("consistent_test_dataset/task-recognition_stim.json", inheritance_metadata)
    
    # Subject 1 files
    sub1_image_metadata = {
        "Technical": {
            "StimulusType": "Image",
            "FileFormat": "png",
            "Resolution": [800, 600],
            "ColorSpace": "RGB"
        },
        "Study": {
            "StimulusID": "face_001"
        },
        "Categories": {
            "PrimaryCategory": "faces",
            "ContentTags": ["human", "neutral_expression"]
        },
        "Metadata": {
            "SchemaVersion": "1.0.0"
        }
    }
    
    sub1_audio_metadata = {
        "Technical": {
            "StimulusType": "Audio",
            "FileFormat": "wav",
            "SampleRate": 44100,
            "Duration": 2.0,
            "Channels": 1
        },
        "Study": {
            "StimulusID": "word_001"
        },
        "Categories": {
            "PrimaryCategory": "speech",
            "ContentTags": ["word", "german"]
        },
        "Metadata": {
            "SchemaVersion": "1.0.0"
        }
    }
    
    # Subject 2 files (consistent structure)
    sub2_image_metadata = {
        "Technical": {
            "StimulusType": "Image",
            "FileFormat": "png",
            "Resolution": [800, 600],
            "ColorSpace": "RGB"
        },
        "Study": {
            "StimulusID": "face_002"
        },
        "Categories": {
            "PrimaryCategory": "faces",
            "ContentTags": ["human", "smiling"]
        },
        "Metadata": {
            "SchemaVersion": "1.0.0"
        }
    }
    
    sub2_audio_metadata = {
        "Technical": {
            "StimulusType": "Audio",
            "FileFormat": "wav",
            "SampleRate": 44100,
            "Duration": 2.0,
            "Channels": 1
        },
        "Study": {
            "StimulusID": "word_002"
        },
        "Categories": {
            "PrimaryCategory": "speech",
            "ContentTags": ["word", "german"]
        },
        "Metadata": {
            "SchemaVersion": "1.0.0"
        }
    }
    
    # Create files and metadata
    create_dummy_image("consistent_test_dataset/sub-001/image/sub-001_task-recognition_run-01_stim.png", 800, 600)
    create_sidecar_json("consistent_test_dataset/sub-001/image/sub-001_task-recognition_run-01_stim.json", sub1_image_metadata)
    
    create_dummy_audio("consistent_test_dataset/sub-001/audio/sub-001_task-recognition_run-01_stim.wav", 2.0)
    create_sidecar_json("consistent_test_dataset/sub-001/audio/sub-001_task-recognition_run-01_stim.json", sub1_audio_metadata)
    
    create_dummy_image("consistent_test_dataset/sub-002/image/sub-002_task-recognition_run-01_stim.png", 800, 600)
    create_sidecar_json("consistent_test_dataset/sub-002/image/sub-002_task-recognition_run-01_stim.json", sub2_image_metadata)
    
    create_dummy_audio("consistent_test_dataset/sub-002/audio/sub-002_task-recognition_run-01_stim.wav", 2.0)
    create_sidecar_json("consistent_test_dataset/sub-002/audio/sub-002_task-recognition_run-01_stim.json", sub2_audio_metadata)
    
    print("✅ Consistent dataset created with inheritance!")
    
    # Original test files for comparison
    print("\nCreating test_dataset files for error demonstration...")
    
    # These will have problems to show validator functionality
    problematic_metadata = {
        "Technical": {
            "StimulusType": "Image",
            "FileFormat": "png",
            "Resolution": [800, 600]
            # Missing required ColorSpace
        },
        "Study": {
            "StudyID": "STUDY_2024_002",
            "TaskName": "facerecognition",
            "StimulusID": "face_test"
        },
        "Categories": {
            "PrimaryCategory": "faces",
            "StudyDomain": "social"
        },
        "Metadata": {
            "Creator": "Demo",
            "CreationDate": "2024-01-15"
        }
    }
    
    # Create some problematic files
    os.makedirs("test_dataset/sub-001/ses-001/image", exist_ok=True)
    create_dummy_image("test_dataset/sub-001/ses-001/image/sub-001_ses-001_task-facerecognition_run-01_stim.png", 800, 600)
    create_sidecar_json("test_dataset/sub-001/ses-001/image/sub-001_ses-001_task-facerecognition_run-01_stim.json", problematic_metadata)

if __name__ == "__main__":
    try:
        main()
        print("✅ Dummy files created successfully!")
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Install with: pip install Pillow numpy")
    except Exception as e:
        print(f"❌ Error creating files: {e}")
