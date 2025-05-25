# 🆘 Advanced Survival Assistant v2.0

An AI-powered emergency survival assistant with real-time voice interaction capabilities. This intelligent system provides immediate, actionable survival guidance through voice commands and emergency protocols.

## 🌟 Features

### Core Capabilities
- **🎤 Real-time Voice Recognition** - Continuous listening with live feedback
- **🤖 AI-Powered Responses** - Context-aware survival guidance using local AI models
- **🚨 Emergency Priority System** - Immediate response to critical situations
- **🗣️ Text-to-Speech** - Natural voice responses with customizable settings
- **⚡ Wake Word Activation** - Hands-free emergency activation
- **🔄 Offline Operation** - Works without internet when properly configured

### Advanced Features
- **📊 Live Audio Feedback** - Real-time speech recognition display
- **⚙️ Configuration Management** - Persistent settings with validation
- **📝 Chat Export** - Save conversation logs for reference
- **🎯 Emergency Mode** - Prioritized processing for urgent situations
- **🛡️ Error Recovery** - Robust error handling and recovery mechanisms
- **🎨 Modern UI** - Dark theme with responsive design

## 🏗️ Architecture

The application consists of several interconnected components:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Audio Input   │◄──►│  AI Interface   │◄──►│   GUI System    │
│  (Vosk + PyAudio) │    │   (Ollama)      │    │   (Tkinter)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Speech Recognition│    │ Response Generation│    │ Status Management│
│ & Wake Words    │    │ & Safety Checks │    │ & User Feedback │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔧 Prerequisites

### System Requirements
- **Operating System**: Windows 10+, macOS 10.14+, or Linux (Ubuntu 18.04+)
- **Python**: 3.8 or higher
- **RAM**: Minimum 4GB (8GB recommended for AI models)
- **Storage**: 2GB free space (for models and dependencies)
- **Audio**: Working microphone and speakers/headphones

### Required Software
1. **Python 3.8+** with pip
2. **Ollama** - Local AI model server
3. **Audio drivers** - Properly configured microphone input

## 📦 Installation

### Step 1: Clone the Repository
```bash
git clone https://github.com/yourusername/survival-assistant.git
cd survival-assistant
```

### Step 2: Set Up Python Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Install Ollama
Download and install Ollama from [https://ollama.ai](https://ollama.ai)

**Windows:**
```bash
# Download installer from website and run
```

**macOS:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### Step 5: Install AI Model
```bash
# Start Ollama service (if not auto-started)
ollama serve

# In a new terminal, pull the recommended model
ollama pull gemma2:9b

# Or use a smaller model for limited resources
ollama pull gemma2:2b
```

### Step 6: Download Vosk Speech Model(NOT NEEDED AS THE MODEL IS DOWNLOADED ALREADY ,BUT U CAN DOWNLOAD THE MODEL AND EXTRACT ZIP HERE )
```bash
# Create models directory
mkdir vosk-models
cd vosk-models

# Download and extract Vosk model (choose appropriate size)
# Small model (~50MB) - faster but less accurate
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip

# OR Large model (~1.8GB) - more accurate but slower
wget https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip
unzip vosk-model-en-us-0.22.zip

cd ..
```

## 🚀 Quick Start

### 1. Start Ollama Service
```bash
ollama serve
```

### 2. Run the Application
```bash
python survival_assistant.py
```

### 3. First Time Setup
The application will create a default configuration file (`assistant_config.json`) on first run. You may need to adjust:

- **Model path**: Update `vosk_model_path` to point to your downloaded Vosk model
- **AI model**: Change `model_name` if using a different Ollama model
- **Wake words**: Customize activation phrases

### 4. Test Your Setup
1. Click "Test AI Connection" in the Tools menu
2. Click "Test Voice Input" to verify microphone
3. Try saying one of the wake words followed by a question

## ⚙️ Configuration

### Configuration File Structure
```json
{
  "model_name": "gemma2:9b",
  "ollama_url": "http://localhost:11434/api/generate",
  "wake_words": ["survival assistant", "emergency help", "assistant", "help me"],
  "vosk_model_path": "./vosk-models/vosk-model-small-en-us-0.15",
  "audio_settings": {
    "sample_rate": 16000,
    "chunk_size": 8000,
    "channels": 1,
    "timeout_default": 8,
    "timeout_emergency": 15
  },
  "tts_settings": {
    "rate": 190,
    "volume": 0.9
  },
  "ui_settings": {
    "auto_scroll": true,
    "max_chat_lines": 1000,
    "theme": "dark"
  }
}
```

### Customizing Settings
1. **Through GUI**: Use Settings menu for easy configuration
2. **Direct Edit**: Modify `assistant_config.json` (restart required)
3. **Command Line**: Some settings can be overridden via environment variables

## 🎯 Usage Guide

### Voice Commands

#### Wake Word Activation
Say any configured wake word followed by your emergency description:
- "Survival assistant, I'm lost in the woods"
- "Emergency help, I need first aid for a cut"
- "Assistant, how do I purify water?"

#### Direct Emergency Commands
These work without wake words:
- "Emergency - [situation]"
- "Help - [problem]"
- "Urgent - [issue]"

#### Question Formats
- "How do I [action]?"
- "What should I do if [situation]?"
- "Where can I find [resource]?"
- "When should I [action]?"

### Button Controls

#### 🚨 Emergency Voice Input
- Activates emergency mode with extended timeout
- Prioritizes response processing
- Optimized for critical situations

#### 🎤 Voice Command
- Standard voice input mode
- Good for general questions
- Regular processing priority

#### GUI Features
- **Real-time feedback** during speech recognition
- **Chat history** with timestamps and color coding
- **Export functionality** for saving conversations
- **Status indicators** for system health

## 🔧 Troubleshooting

### Common Issues

#### "Voice recognition not available"
**Cause**: Missing Vosk or PyAudio dependencies
**Solution**:
```bash
pip install vosk pyaudio
# On Linux, you might need:
sudo apt-get install portaudio19-dev python3-pyaudio
```

#### "AI service connection failed"
**Cause**: Ollama service not running or wrong URL
**Solution**:
```bash
# Start Ollama
ollama serve

# Verify service
curl http://localhost:11434/api/tags
```

#### "Model not found"
**Cause**: AI model not installed
**Solution**:
```bash
ollama list  # Check installed models
ollama pull gemma2:9b  # Install model
```

#### "Microphone not working"
**Cause**: Audio device issues or permissions
**Solution**:
- Check microphone permissions
- Test microphone in other applications
- Try different audio device in system settings

#### Performance Issues
**Symptoms**: Slow responses, high CPU usage
**Solutions**:
- Use smaller AI model (`gemma2:2b` instead of `gemma2:9b`)
- Use smaller Vosk model
- Close unnecessary applications
- Ensure adequate RAM available

### Debug Mode
Enable detailed logging by setting environment variable:
```bash
export LOG_LEVEL=DEBUG
python survival_assistant.py
```

### Log Files
- Application logs: `survival_assistant.log`
- Configuration backups: `assistant_config.json.backup`

## 🛠️ Development

### Project Structure
```
survival-assistant/
├── survival_assistant.py      # Main application file
├── assistant_config.json      # Configuration file
├── requirements.txt           # Python dependencies
├── survival_assistant.log     # Application logs
├── vosk-models/              # Speech recognition models
├── README.md                 # This file
└── docs/                     # Additional documentation
    ├── API.md               # API documentation
    ├── TROUBLESHOOTING.md   # Extended troubleshooting
    └── CONTRIBUTING.md      # Contribution guidelines
```

### Key Components

#### ConfigManager
Handles configuration loading, validation, and persistence.

#### AudioManager
Manages microphone input, speech recognition, and text-to-speech synthesis.

#### AIInterface
Communicates with Ollama AI service and handles response generation.

#### EnhancedSurvivalAssistant
Core logic coordinator that manages all components and handles user interactions.

#### ModernAssistantGUI
Tkinter-based graphical interface with modern styling and responsive design.

### Adding New Features

#### Custom Wake Words
Edit the `wake_words` array in configuration:
```json
"wake_words": ["custom phrase", "emergency help", "survival mode"]
```

#### Custom AI Models
Use any Ollama-compatible model:
```bash
ollama pull your-custom-model
# Update model_name in config
```

#### Extended Audio Formats
Modify `AudioManager` to support additional formats or sample rates.

## 📋 Dependencies

### Core Dependencies
```
requests>=2.31.0         # HTTP requests for AI communication
pyttsx3>=2.90           # Text-to-speech synthesis
vosk>=0.3.45            # Speech recognition
pyaudio>=0.2.11         # Audio input/output
```

### System Dependencies
- **PortAudio** (for PyAudio)
- **Ollama** (AI model server)
- **Python 3.8+** with tkinter support

### Optional Dependencies
- **matplotlib** - For audio visualization (future feature)
- **scipy** - For advanced audio processing
- **numpy** - For numerical computations

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

### Areas for Contribution
- Additional survival knowledge modules
- UI/UX improvements
- Performance optimizations
- Multi-language support
- Mobile app development
- Integration with emergency services

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Vosk** - Open-source speech recognition toolkit
- **Ollama** - Local AI model serving platform
- **OpenAI** - For inspiration in conversational AI
- **Survival community** - For domain expertise and testing

## 📞 Support

### Getting Help
1. **Documentation**: Check this README and docs/ folder
2. **Issues**: Open a GitHub issue for bugs or feature requests
3. **Discussions**: Use GitHub Discussions for questions
4. **Community**: Join our Discord server (link in repository)

### Emergency Disclaimer
⚠️ **Important**: This software is for educational and preparedness purposes only. In real emergencies:
- **Call emergency services first** (911, 112, etc.)
- Use this tool as supplementary guidance only
- Always prioritize professional emergency response
- Test and familiarize yourself with the system before emergencies

### Version History

#### v2.0.0 (Current)
- Complete rewrite with enhanced architecture
- Improved voice recognition with live feedback
- Better error handling and recovery
- Modern GUI with dark theme
- Configuration management system
- Chat export functionality

#### v1.0.0
- Initial release with basic voice recognition
- Simple AI integration
- Basic GUI interface

---

**Stay prepared, stay safe! 🛡️**

For the latest updates and community support, visit our [GitHub repository](https://github.com/yourusername/survival-assistant).
