# 🌿 Tobacco AI Assistant

A WhatsApp-based AI assistant that helps tobacco farmers detect leaf diseases using YOLOv8 computer vision. Built for Zimbabwean farmers with support for local farming practices.

![Version](https://img.shields.io/badge/version-1.0.0-green)
![Python](https://img.shields.io/badge/python-3.10-blue)
![License](https://img.shields.io/badge/license-MIT-orange)

## 📋 Table of Contents
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [Environment Variables](#-environment-variables)
- [Deployment](#-deployment)
- [Usage Guide](#-usage-guide)
- [Disease Detection](#-disease-detection)
- [Educational Content](#-educational-content)
- [API Reference](#-api-reference)
- [Contributing](#-contributing)
- [License](#-license)
- [Contact](#-contact)

## 🚀 Features

### 🔍 Disease Detection
- Upload leaf photos for instant disease diagnosis
- 14 trained disease classes including:
  - Black Spot, Black Shank, Early/Late Blight
  - Leaf Mold, Leaf Spot, Powdery Mildew
  - Septoria Blight, Tobacco Viruses
  - Spider Mites, and more
- Confidence scoring and filtering
- Image quality validation

### 📚 Educational Content
- **Planting Guide**: Nursery prep, transplanting, spacing
- **Fertilizer Guide**: Application rates, timing, types
- **Harvesting Guide**: Priming methods, curing, handling
- **Marketing Guide**: Grading, 2026 season dates, biometric ID
- **Full Growth Journey**: Seed to sale

### 👨‍🌾 Expert Connection
- Connect with real agronomists
- Submit questions via WhatsApp
- Track request status
- Expert assignment system

### 📊 User Features
- **Scan History**: Track past diagnoses
- **Interactive Menu**: Easy navigation
- **Feedback System**: Send comments to admin
- **Daily Tips**: Random farming tips
- **Fun Facts**: Educational entertainment

### 🌍 Multi-language (Coming Soon)
- English (current)
- Shona (in development)
- Ndebele (in development)

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Python 3.10 + Flask |
| **AI Model** | YOLOv8 (Custom trained) |
| **Database** | Firebase Firestore |
| **Messaging** | WhatsApp Cloud API |
| **Hosting** | Render |
| **Image Processing** | OpenCV, Pillow |
| **Monitoring** | Custom logging |

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- WhatsApp Business API access
- Firebase project
- Trained YOLO model (`best.pt`)

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/tuneinzw-sudo/tobaccodeseedetection.git
   cd tobaccodeseedetection