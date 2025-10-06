#!/usr/bin/env python3
"""
Generate dummy files for new modalities (EEG, Eyetracking, Physiological, Behavior)
"""

import os
import json
import csv
import random
import math
from datetime import datetime, timedelta

def create_eeg_dummy_data(filepath):
    """Create a dummy EEG data file (simplified header)"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    # Create a simple text representation of EEG data
    with open(filepath, 'w') as f:
        f.write("# Dummy EEG data file\n")
        f.write("# Channels: Fp1, Fp2, F3, F4, C3, C4, P3, P4, O1, O2\n")
        f.write("# Sampling Rate: 500 Hz\n")
        for i in range(100):  # 100 sample points
            # Generate 10 channels of dummy data
            values = [f"{random.uniform(-50, 50):.2f}" for _ in range(10)]
            f.write("\t".join(values) + "\n")

def create_eyetracking_dummy_data(filepath):
    """Create a dummy eyetracking TSV file"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        # Header
        writer.writerow(['timestamp', 'x_gaze', 'y_gaze', 'pupil_diameter', 'fixation_id', 'saccade_id'])
        
        # Generate dummy eyetracking data
        for i in range(500):  # 500 samples
            timestamp = i * 2  # 500 Hz sampling
            x_gaze = random.uniform(0, 1920)  # Screen coordinates
            y_gaze = random.uniform(0, 1080)
            pupil = random.uniform(2.5, 6.0)  # Pupil diameter in mm
            fix_id = i // 50 if i % 50 < 45 else -1  # Fixation periods
            sacc_id = -1 if fix_id != -1 else (i // 5)  # Saccades between fixations
            writer.writerow([timestamp, f"{x_gaze:.2f}", f"{y_gaze:.2f}", f"{pupil:.2f}", fix_id, sacc_id])

def create_physiological_dummy_data(filepath):
    """Create a dummy physiological CSV file"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        # Header
        writer.writerow(['timestamp', 'ECG', 'GSR', 'respiration', 'temperature'])
        
        # Generate dummy physiological data
        base_hr = 70  # Base heart rate
        base_gsr = 10  # Base skin conductance
        for i in range(1000):  # 1000 samples (100 Hz for 10 seconds)
            timestamp = i * 0.01  # 100 Hz sampling
            ecg = base_hr + random.uniform(-5, 5) + 20 * (1 if i % 60 < 5 else 0)  # Heartbeat spikes
            gsr = base_gsr + random.uniform(-1, 3) + (5 if 300 < i < 400 else 0)  # Stress response
            resp = 15 + 5 * math.sin(i * 0.1) + random.uniform(-1, 1)  # Breathing pattern
            temp = 36.5 + random.uniform(-0.2, 0.2)  # Body temperature
            writer.writerow([f"{timestamp:.2f}", f"{ecg:.2f}", f"{gsr:.2f}", f"{resp:.2f}", f"{temp:.2f}"])

def create_behavioral_dummy_data(filepath):
    """Create a dummy behavioral TSV file"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        # Header
        writer.writerow(['trial', 'condition', 'stimulus', 'response', 'reaction_time', 'accuracy', 'confidence'])
        
        # Generate dummy behavioral data
        conditions = ['congruent', 'incongruent']
        stimuli = ['red_word', 'blue_word', 'green_word', 'yellow_word']
        responses = ['red', 'blue', 'green', 'yellow']
        
        for trial in range(1, 101):  # 100 trials
            condition = random.choice(conditions)
            stimulus = random.choice(stimuli)
            response = random.choice(responses)
            
            # Congruent trials are faster and more accurate
            if condition == 'congruent' and stimulus.split('_')[0] == response:
                rt = random.uniform(400, 600)  # Faster RTs
                accuracy = 1 if random.random() > 0.05 else 0  # 95% accuracy
            else:
                rt = random.uniform(500, 800)  # Slower RTs
                accuracy = 1 if random.random() > 0.15 else 0  # 85% accuracy
                
            confidence = random.uniform(1, 7)  # 1-7 confidence scale
            writer.writerow([trial, condition, stimulus, response, f"{rt:.0f}", accuracy, f"{confidence:.1f}"])

def create_demo_metadata():
    """Create comprehensive demo dataset with new modalities"""
    print("Creating comprehensive demo dataset with new modalities...")
    
    # Create directory structure
    base_dir = "comprehensive_demo_dataset"
    
    # Dataset description
    dataset_desc = {
        "Name": "Comprehensive Psychology Demo Dataset",
        "BIDSVersion": "1.6.0",
        "DatasetType": "raw", 
        "Authors": ["Psycho-Validator Team"],
        "License": "CC0",
        "Acknowledgements": "Demo dataset for psycho-validator showcase"
    }
    
    os.makedirs(base_dir, exist_ok=True)
    with open(f"{base_dir}/dataset_description.json", 'w') as f:
        json.dump(dataset_desc, f, indent=2)
    
    # Participants file
    participants_data = [
        ["participant_id", "age", "sex", "handedness"],
        ["sub-001", "25", "F", "R"],
        ["sub-002", "30", "M", "R"],
        ["sub-003", "22", "F", "L"]
    ]
    
    with open(f"{base_dir}/participants.tsv", 'w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerows(participants_data)
    
    # Create inheritance metadata
    inheritance_metadata = {
        "Study": {
            "StudyID": "MULTI_MODAL_2024",
            "TaskName": "multimodal_experiment"
        },
        "Categories": {
            "StudyDomain": "cognitive"
        },
        "Metadata": {
            "SchemaVersion": "1.0.0",
            "Creator": "Psycho-Validator Demo Team",
            "CreationDate": "2024-09-11",
            "Institution": "University of Graz Psychology Institute"
        }
    }
    
    with open(f"{base_dir}/task-multimodal_experiment_stim.json", 'w') as f:
        json.dump(inheritance_metadata, f, indent=2)
    
    # Subject 001 - Multiple modalities
    for modality, file_ext, creator_func, metadata in [
        ("eeg", "edf", create_eeg_dummy_data, {
            "Technical": {
                "StimulusType": "EEG",
                "FileFormat": "edf",
                "SamplingRate": 500,
                "ChannelCount": 10,
                "ChannelLayout": "10-20",
                "ReferenceType": "common_average"
            },
            "Study": {
                "Paradigm": "oddball",
                "TrialCount": 200,
                "BaselinePeriod": [-200, 0]
            },
            "Categories": {
                "AnalysisType": ["erp"],
                "ERPComponents": ["P3", "N1"],
                "CognitiveProcesses": ["attention"],
                "DataQuality": "excellent"
            }
        }),
        ("eyetracking", "tsv", create_eyetracking_dummy_data, {
            "Technical": {
                "StimulusType": "Eyetracking",
                "FileFormat": "tsv",
                "SamplingRate": 500,
                "TrackingMode": "binocular",
                "EyeTracked": "both",
                "CalibrationMethod": "9_point",
                "CalibrationAccuracy": 0.5,
                "ScreenResolution": [1920, 1080],
                "ViewingDistance": 60
            },
            "Study": {
                "ParadigmType": "free_viewing",
                "StimulusPresentation": {
                    "Duration": 5.0,
                    "TrialCount": 50,
                    "InterTrialInterval": 1.0
                }
            },
            "Categories": {
                "AnalysisMetrics": ["fixation_duration", "saccade_amplitude"],
                "CognitiveProcesses": ["visual_search", "attention"],
                "DataQuality": "good"
            }
        }),
        ("physiological", "csv", create_physiological_dummy_data, {
            "Technical": {
                "StimulusType": "Physiological",
                "FileFormat": "csv",
                "MeasurementType": ["ECG", "GSR", "respiration", "temperature"],
                "SamplingRate": 100,
                "ChannelCount": 4
            },
            "Study": {
                "ParadigmType": "stress_induction",
                "BaselinePeriod": [0, 60],
                "RecoveryPeriod": [240, 300]
            },
            "Categories": {
                "AnalysisMetrics": ["heart_rate", "skin_conductance"],
                "StressIndicators": ["acute_stress", "sympathetic_activation"],
                "DataQuality": "excellent"
            }
        }),
        ("behavior", "tsv", create_behavioral_dummy_data, {
            "Technical": {
                "StimulusType": "Behavior",
                "FileFormat": "tsv",
                "ResponseType": ["keypress"],
                "SoftwarePlatform": "PsychoPy"
            },
            "Study": {
                "TaskType": "reaction_time",
                "ExperimentalDesign": "within_subjects",
                "TrialStructure": {
                    "TrialCount": 100,
                    "BlockCount": 4,
                    "TrialsPerBlock": 25
                }
            },
            "Categories": {
                "CognitiveDomains": ["attention", "executive_function"],
                "PerformanceMetrics": ["reaction_time", "accuracy"],
                "TaskDifficulty": "moderate"
            }
        })
    ]:
        # Create data file
        data_file = f"{base_dir}/sub-001/{modality}/sub-001_task-multimodal_experiment_run-01_stim.{file_ext}"
        creator_func(data_file)
        
        # Create metadata file
        metadata_copy = metadata.copy()
        metadata_copy["Metadata"] = {"SchemaVersion": "1.0.0"}
        
        json_file = f"{base_dir}/sub-001/{modality}/sub-001_task-multimodal_experiment_run-01_stim.json"
        with open(json_file, 'w') as f:
            json.dump(metadata_copy, f, indent=2)
    
    print("✅ Comprehensive demo dataset created successfully!")
    print(f"📂 Location: {base_dir}/")
    print("🧠 Includes: EEG, Eyetracking, Physiological, Behavioral data")
    print("📋 With proper metadata and inheritance structure")

if __name__ == "__main__":
    create_demo_metadata()
