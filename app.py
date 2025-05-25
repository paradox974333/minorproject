import os
import json
import time
import queue
import threading
import requests
import pyttsx3
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from tkinter import font as tkFont
import datetime
import logging
from typing import Optional, Callable
import contextlib
import sys
import signal

try:
    from vosk import Model, KaldiRecognizer
    import pyaudio
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

# Enhanced configuration with validation
CONFIG_FILE = "assistant_config.json"
DEFAULT_CONFIG = {
    "model_name": "Android_Artisan/Gemma3-Android:latest",
    "ollama_url": "http://localhost:11434/api/generate",
    "wake_words": ["survival assistant", "emergency help", "assistant", "help me"],
    "vosk_model_path": "./vosk-model-small-en-us-0.15",
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
        "auto_scroll": True,
        "max_chat_lines": 1000,
        "theme": "dark"
    }
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('survival_assistant.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

### Configuration Management
class ConfigManager:
    """Manages configuration loading, saving, and validation."""
    
    @staticmethod
    def load_config() -> dict:
        if not os.path.exists(CONFIG_FILE):
            ConfigManager.save_config(DEFAULT_CONFIG)
            logger.info("Created default configuration file")
        
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            return ConfigManager.validate_config(config)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return DEFAULT_CONFIG
    
    @staticmethod
    def save_config(config: dict):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    @staticmethod
    def validate_config(config: dict) -> dict:
        """Validates config and merges with defaults."""
        validated = DEFAULT_CONFIG.copy()
        
        def deep_update(base, update):
            for key, value in update.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_update(base[key], value)
                else:
                    base[key] = value
        
        deep_update(validated, config)
        return validated

### Audio Management
class AudioManager:
    """Handles audio input and text-to-speech with improved error handling."""
    
    def __init__(self, config: dict):
        self.config = config
        self.audio_settings = config["audio_settings"]
        self.tts_settings = config["tts_settings"]
        
        self.audio_device = None
        self.stream = None
        self.tts_engine = None
        self.tts_queue = queue.Queue()
        self.tts_thread = None
        self._tts_stop_event = threading.Event()
        
        self.setup_audio_input()
        self.setup_text_to_speech()
    
    def setup_audio_input(self) -> bool:
        """Sets up audio input with robust error handling."""
        if not VOSK_AVAILABLE:
            logger.warning("Vosk not available - voice input disabled")
            return False
        
        try:
            if not os.path.isdir(self.config["vosk_model_path"]):
                logger.error(f"Vosk model not found at: {self.config['vosk_model_path']}")
                return False
            
            self.vosk_model = Model(self.config["vosk_model_path"])
            self.recognizer = KaldiRecognizer(self.vosk_model, self.audio_settings["sample_rate"])
            
            self.audio_device = pyaudio.PyAudio()
            device_info = self.audio_device.get_default_input_device_info()
            logger.info(f"Using audio device: {device_info['name']}")
            
            self.stream = self.audio_device.open(
                format=pyaudio.paInt16,
                channels=self.audio_settings["channels"],
                rate=self.audio_settings["sample_rate"],
                input=True,
                frames_per_buffer=self.audio_settings["chunk_size"]
            )
            
            self.stream.start_stream()
            logger.info("Audio input initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize audio input: {e}")
            self.cleanup_audio()
            return False
    
    def setup_text_to_speech(self) -> bool:
        """Sets up text-to-speech with enhanced configuration."""
        try:
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', self.tts_settings["rate"])
            self.tts_engine.setProperty('volume', self.tts_settings["volume"])
            
            voices = self.tts_engine.getProperty('voices')
            if voices:
                for voice in voices:
                    if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                        self.tts_engine.setProperty('voice', voice.id)
                        break
                else:
                    self.tts_engine.setProperty('voice', voices[0].id)
            
            self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
            self.tts_thread.start()
            logger.info("Text-to-speech initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize TTS: {e}")
            return False
    
    def _tts_worker(self):
        """Processes TTS queue with error handling."""
        while not self._tts_stop_event.is_set():
            try:
                text = self.tts_queue.get(timeout=1)
                if text is None:
                    break
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"TTS error: {e}")
    
    def speak(self, text: str):
        """Queues text for speech synthesis."""
        if self.tts_engine and not self._tts_stop_event.is_set():
            self.tts_queue.put(text)
    
    def listen(self, timeout: float = 8, callback: Optional[Callable] = None) -> Optional[str]:
        """Listens for audio input with live feedback."""
        if not self.stream or not self.stream.is_active():
            return None
        
        start_time = time.time()
        result_text = ""
        last_partial = ""
        silence_start = None
        min_speech_duration = 0.5
        
        while time.time() - start_time < timeout:
            try:
                data = self.stream.read(4000, exception_on_overflow=False)
                
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    result_text = result.get("text", "").strip()
                    if result_text and time.time() - start_time > min_speech_duration:
                        return result_text.lower()
                else:
                    partial_result = json.loads(self.recognizer.PartialResult())
                    current_partial = partial_result.get("partial", "")
                    
                    if current_partial != last_partial:
                        last_partial = current_partial
                        if callback and current_partial:
                            callback(f"🗣️ {current_partial}...")
                        if current_partial:
                            silence_start = None
                        elif silence_start is None and last_partial:
                            silence_start = time.time()
                    
                    if silence_start and time.time() - silence_start > 2:
                        if last_partial:
                            return last_partial.lower()
            except Exception as e:
                logger.warning(f"Audio processing error: {e}")
                continue
        
        return result_text.lower() if result_text else None
    
    def cleanup_audio(self):
        """Cleans up audio resources."""
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.audio_device:
                self.audio_device.terminate()
        except Exception as e:
            logger.error(f"Audio cleanup error: {e}")
    
    def shutdown(self):
        """Shuts down audio manager."""
        self._tts_stop_event.set()
        if self.tts_thread and self.tts_thread.is_alive():
            self.tts_queue.put(None)
            self.tts_thread.join(timeout=2)
        self.cleanup_audio()

### AI Interface
class AIInterface:
    """Manages AI communication with enhanced prompting and retry logic."""
    
    def __init__(self, config: dict):
        self.config = config
        self.model_name = config["model_name"]
        self.ollama_url = config["ollama_url"]
        self.session = requests.Session()
        self.session.timeout = 30
        self.test_connection()
    
    def test_connection(self) -> bool:
        """Tests connection to Ollama service."""
        try:
            list_url = self.ollama_url.replace('/api/generate', '/api/tags')
            response = self.session.get(list_url, timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                if self.model_name not in model_names:
                    logger.warning(f"Model {self.model_name} not found. Available: {model_names}")
                else:
                    logger.info(f"AI service connected. Using model: {self.model_name}")
                return True
        except Exception as e:
            logger.error(f"AI service connection failed: {e}")
        return False
    
    def generate_response(self, prompt: str, emergency: bool = False) -> Optional[str]:
        """Generates AI response with tailored prompts."""
        if emergency:
            system_prompt = """You are an emergency survival assistant. Your response must be:
1. IMMEDIATE and ACTIONABLE
2. PRIORITIZED by urgency
3. CLEAR and CONCISE
4. POTENTIALLY LIFE-SAVING

Provide step-by-step emergency guidance. Start with the most critical actions first."""
        else:
            system_prompt = """You are a knowledgeable survival assistant. Provide practical, safe, and helpful advice. 
Be clear, concise, and prioritize safety in all recommendations."""
        
        full_prompt = f"{system_prompt}\n\nSituation: {prompt}\n\nResponse:"
        
        data = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": 0.1 if emergency else 0.3,
                "num_predict": 300 if emergency else 500,
                "top_p": 0.9,
                "repeat_penalty": 1.1
            }
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.post(self.ollama_url, json=data, timeout=30)
                if response.status_code == 200:
                    result = response.json().get("response", "").strip()
                    if result:
                        return self._clean_response(result)
                    else:
                        logger.warning("Empty response from AI")
                elif response.status_code == 404:
                    logger.error(f"Model {self.model_name} not found")
                    break
                else:
                    logger.error(f"AI request failed with status {response.status_code}")
            except requests.exceptions.Timeout:
                logger.warning(f"AI request timeout (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(1)
            except Exception as e:
                logger.error(f"AI request error: {e}")
                break
        return None
    
    def _clean_response(self, text: str) -> str:
        """Cleans response for better speech synthesis."""
        text = text.replace('**', '').replace('*', '').replace('#', '').replace('```', '')
        text = text.replace('\n\n', '. ').replace('\n', '. ')
        text = text.replace('..', '.').replace('  ', ' ')
        return text.strip()

### Core Assistant Logic
class EnhancedSurvivalAssistant:
    """Coordinates audio, AI, and GUI components."""
    
    def __init__(self, gui_callback, status_callback, listening_callback):
        self.config = ConfigManager.load_config()
        self.gui_callback = gui_callback
        self.status_callback = status_callback
        self.listening_callback = listening_callback
        
        self.audio_manager = AudioManager(self.config)
        self.ai_interface = AIInterface(self.config)
        
        self._stop_event = threading.Event()
        self.is_processing = False
        self.is_listening = False
        self.wake_words = [word.lower() for word in self.config["wake_words"]]
        self.main_thread = None
    
    def start(self):
        """Starts the assistant."""
        welcome_msg = "Advanced Survival Assistant is now active and monitoring for emergencies."
        self.speak(welcome_msg)
        
        if self.audio_manager.stream:
            self.main_thread = threading.Thread(target=self._main_loop, daemon=True)
            self.main_thread.start()
            self.status_callback("🟢 Ready", "#2196F3")
        else:
            self.speak("Voice recognition is unavailable. Manual mode only.")
            self.status_callback("⚠️ Voice Disabled", "#F44336")
    
    def speak(self, text: str):
        """Speaks and displays text."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.gui_callback(f"[{timestamp}] ASSISTANT: {text}\n", "assistant")
        self.audio_manager.speak(text)
    
    def _main_loop(self):
        """Main listening loop with improved wake word detection."""
        consecutive_errors = 0
        max_errors = 5
        
        while not self._stop_event.is_set():
            if self.is_processing:
                time.sleep(0.1)
                continue
            
            try:
                self.is_listening = True
                self.listening_callback(True)
                
                command = self.audio_manager.listen(
                    timeout=5,
                    callback=lambda partial: self.gui_callback(f"{partial}\n", "partial", True)
                )
                
                self.is_listening = False
                self.listening_callback(False)
                
                if command:
                    consecutive_errors = 0
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                    self.gui_callback(f"[{timestamp}] YOU: {command}\n", "user")
                    
                    if any(wake_word in command for wake_word in self.wake_words):
                        self.handle_wake_word_activation()
                    elif any(word in command for word in ['emergency', 'urgent', 'help', 'danger']):
                        self.process_command(command, emergency=True)
                    elif any(word in command for word in ['how', 'what', 'when', 'where', 'why']):
                        self.process_command(command, emergency=False)
                    elif any(word in command for word in ['exit', 'quit', 'stop', 'shutdown']):
                        self.shutdown()
                        break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Main loop error: {e}")
                if consecutive_errors >= max_errors:
                    self.speak("I'm experiencing technical difficulties. Please restart the application.")
                    break
                time.sleep(1)
    
    def handle_wake_word_activation(self):
        """Handles wake word activation."""
        self.speak("I'm ready to help with your emergency. Please describe the situation.")
        
        follow_up = self.audio_manager.listen(
            timeout=self.config["audio_settings"]["timeout_emergency"],
            callback=lambda partial: self.gui_callback(f"{partial}\n", "partial", True)
        )
        
        if follow_up:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self.gui_callback(f"[{timestamp}] YOU: {follow_up}\n", "user")
            self.process_command(follow_up, emergency=True)
        else:
            self.speak("I didn't catch that. Please try again or use the emergency voice button.")
    
    def process_command(self, command: str, emergency: bool = False):
        """Processes commands with AI assistance."""
        if self.is_processing:
            return
        
        self.is_processing = True
        
        def process_in_thread():
            try:
                self.status_callback("🤖 Consulting AI", "#673AB7")
                response = self.ai_interface.generate_response(command, emergency)
                if response:
                    self.speak(response)
                else:
                    error_msg = "I'm having trouble accessing the AI service. Please check the connection."
                    if emergency:
                        error_msg += " In a real emergency, please call emergency services immediately."
                    self.speak(error_msg)
            except Exception as e:
                logger.error(f"Command processing error: {e}")
                self.speak("I'm experiencing technical difficulties. Please try again.")
            finally:
                self.is_processing = False
                self.status_callback("🟢 Ready", "#2196F3")
        
        threading.Thread(target=process_in_thread, daemon=True).start()
    
    def manual_voice_input(self, emergency: bool = False) -> bool:
        """Handles manual voice input."""
        if self.is_processing or self.is_listening:
            return False
        
        timeout = self.config["audio_settings"]["timeout_emergency"] if emergency else self.config["audio_settings"]["timeout_default"]
        
        def capture_input():
            self.is_listening = True
            self.listening_callback(True)
            
            if emergency:
                self.gui_callback("🚨 EMERGENCY MODE - Describe your situation clearly...\n", "system")
            else:
                self.gui_callback("🎤 Listening for your command...\n", "system")
            
            command = self.audio_manager.listen(
                timeout=timeout,
                callback=lambda partial: self.gui_callback(f"{partial}\n", "partial", True)
            )
            
            self.is_listening = False
            self.listening_callback(False)
            
            if command:
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                self.gui_callback(f"[{timestamp}] YOU: {command}\n", "user")
                self.process_command(command, emergency=emergency)
            else:
                self.gui_callback("🔇 No clear input detected. Please try again.\n", "system")
        
        threading.Thread(target=capture_input, daemon=True).start()
        return True
    
    def shutdown(self):
        """Performs clean shutdown."""
        self._stop_event.set()
        self.speak("Shutting down survival assistant. Stay safe.")
        if self.main_thread and self.main_thread.is_alive():
            self.main_thread.join(timeout=2)
        self.audio_manager.shutdown()

### Graphical User Interface
class ModernAssistantGUI:
    """Modernized GUI with enhanced responsiveness."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("🆘 Advanced Survival Assistant v2.0")
        self.root.geometry("1000x800")
        self.root.configure(bg="#0D1117")
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.setup_styles()
        self.setup_fonts()
        self.create_interface()
        
        self.chat_lines = 0
        self.max_chat_lines = 1000
        
        self.assistant = EnhancedSurvivalAssistant(
            self.display_message,
            self.update_status,
            self.set_listening_state
        )
        
        self.initialize_assistant()
        
        self.pulse_state = 0
        self.listening_animation = False
        self.animate_interface()
    
    def setup_styles(self):
        """Configures modern UI styles."""
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        self.style.configure("Modern.TButton",
                           background="#238636",
                           foreground="white",
                           font=("Segoe UI", 11, "bold"),
                           padding=(20, 12),
                           relief="flat",
                           borderwidth=0)
        self.style.map("Modern.TButton",
                      background=[("active", "#2ea043"), ("pressed", "#1a7f37"), ("disabled", "#656d76")])
        
        self.style.configure("Emergency.TButton",
                           background="#da3633",
                           foreground="white",
                           font=("Segoe UI", 12, "bold"),
                           padding=(25, 15),
                           relief="flat",
                           borderwidth=0)
        self.style.map("Emergency.TButton",
                      background=[("active", "#f85149"), ("pressed", "#b62324"), ("disabled", "#656d76")])
    
    def setup_fonts(self):
        """Sets up fonts for readability."""
        self.title_font = tkFont.Font(family="Segoe UI", size=26, weight="bold")
        self.status_font = tkFont.Font(family="Segoe UI", size=14, weight="bold")
        self.chat_font = tkFont.Font(family="Consolas", size=11)
        self.timestamp_font = tkFont.Font(family="Segoe UI", size=9)
    
    def create_interface(self):
        """Creates the complete GUI."""
        self.create_header()
        self.create_status_panel()
        self.create_chat_area()
        self.create_controls()
        self.create_menu()
    
    def create_header(self):
        """Creates header with status indicators."""
        header_frame = tk.Frame(self.root, bg="#0D1117", height=90)
        header_frame.pack(fill="x", padx=20, pady=(20, 10))
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, text="🆘 SURVIVAL ASSISTANT v2.0", font=self.title_font, bg="#0D1117", fg="#58A6FF")
        title_label.pack(side="left", padx=(10, 0), pady=20)
        
        status_frame = tk.Frame(header_frame, bg="#0D1117")
        status_frame.pack(side="right", padx=(0, 10), pady=20)
        
        self.ai_status_frame = tk.Frame(status_frame, bg="#0D1117")
        self.ai_status_frame.pack(side="top", anchor="e")
        self.ai_indicator = tk.Label(self.ai_status_frame, text="●", font=("Segoe UI", 16), bg="#0D1117", fg="#238636")
        self.ai_indicator.pack(side="right")
        tk.Label(self.ai_status_frame, text="AI READY", font=("Segoe UI", 9, "bold"), bg="#0D1117", fg="#7D8590").pack(side="right", padx=(0, 5))
        
        self.voice_status_frame = tk.Frame(status_frame, bg="#0D1117")
        self.voice_status_frame.pack(side="top", anchor="e", pady=(5, 0))
        self.voice_indicator = tk.Label(self.voice_status_frame, text="●", font=("Segoe UI", 16), bg="#0D1117", fg="#238636" if VOSK_AVAILABLE else "#da3633")
        self.voice_indicator.pack(side="right")
        tk.Label(self.voice_status_frame, text="VOICE READY" if VOSK_AVAILABLE else "VOICE DISABLED", font=("Segoe UI", 9, "bold"), bg="#0D1117", fg="#7D8590").pack(side="right", padx=(0, 5))
    
    def create_status_panel(self):
        """Creates status panel with animation."""
        status_frame = tk.Frame(self.root, bg="#161B22", relief="flat", bd=1)
        status_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        self.status_var = tk.StringVar(value="🔄 Initializing")
        self.status_label = tk.Label(status_frame, textvariable=self.status_var, font=self.status_font, bg="#161B22", fg="#58A6FF", pady=15)
        self.status_label.pack(side="left", padx=20)
        
        self.live_indicator = tk.Frame(status_frame, bg="#161B22")
        self.live_indicator.pack(side="right", padx=20, pady=10)
        self.pulse_dot = tk.Label(self.live_indicator, text="●", font=("Segoe UI", 16), bg="#161B22", fg="#238636")
        self.pulse_dot.pack(side="right")
        tk.Label(self.live_indicator, text="LIVE", font=("Segoe UI", 10, "bold"), bg="#161B22", fg="#7D8590").pack(side="right", padx=(0, 5))
    
    def create_chat_area(self):
        """Creates chat area with styled text."""
        chat_frame = tk.Frame(self.root, bg="#0D1117")
        chat_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        self.text_area = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, font=self.chat_font, bg="#0D1117", fg="#E6EDF3", insertbackground="#58A6FF", relief="flat", bd=0, padx=15, pady=15, selectbackground="#264F78", selectforeground="#FFFFFF", state="disabled")
        self.text_area.pack(fill="both", expand=True)
        
        self.text_area.tag_configure("assistant", foreground="#3FB950", font=("Consolas", 11, "bold"))
        self.text_area.tag_configure("user", foreground="#58A6FF", font=("Consolas", 11, "bold"))
        self.text_area.tag_configure("system", foreground="#FFA657", font=("Consolas", 10, "italic"))
        self.text_area.tag_configure("partial", foreground="#7D8590", font=("Consolas", 10, "italic"))
        self.text_area.tag_configure("timestamp", foreground="#484F58", font=self.timestamp_font)
        self.text_area.tag_configure("emergency", foreground="#FF6B6B", font=("Consolas", 11, "bold"))
    
    def create_controls(self):
        """Creates control panel with buttons."""
        controls_frame = tk.Frame(self.root, bg="#0D1117")
        controls_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        emergency_frame = tk.Frame(controls_frame, bg="#0D1117")
        emergency_frame.pack(side="left", fill="x", expand=True)
        
        self.emergency_button = ttk.Button(emergency_frame, text="🚨 EMERGENCY VOICE INPUT", style="Emergency.TButton", command=self.trigger_emergency_input)
        self.emergency_button.pack(side="left", padx=(0, 10))
        
        self.voice_button = ttk.Button(emergency_frame, text="🎤 Voice Command", style="Modern.TButton", command=self.manual_voice_input)
        self.voice_button.pack(side="left", padx=(0, 10))
        
        utility_frame = tk.Frame(controls_frame, bg="#0D1117")
        utility_frame.pack(side="right")
        
        self.clear_button = ttk.Button(utility_frame, text="🗑️ Clear", command=self.clear_chat)
        self.clear_button.pack(side="left", padx=(0, 10))
        
        self.settings_button = ttk.Button(utility_frame, text="⚙️ Settings", command=self.show_settings)
        self.settings_button.pack(side="left", padx=(0, 10))
        
        self.quit_btn = ttk.Button(utility_frame, text="⏻ Shutdown", command=self.quit_app)
        self.quit_btn.pack(side="left")
    
    def create_menu(self):
        """Creates application menu."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export Chat Log", command=self.export_chat)
        file_menu.add_command(label="Clear Chat", command=self.clear_chat)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit_app)
        
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Test AI Connection", command=self.test_ai_connection)
        tools_menu.add_command(label="Test Voice Input", command=self.test_voice_input)
        tools_menu.add_command(label="Settings", command=self.show_settings)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Wake Words", command=self.show_wake_words)
        help_menu.add_command(label="Emergency Commands", command=self.show_emergency_help)
        help_menu.add_command(label="About", command=self.show_about)
    
    def initialize_assistant(self):
        """Initializes assistant in background."""
        def init_thread():
            try:
                self.assistant.start()
            except Exception as e:
                logger.error(f"Assistant initialization error: {e}")
                self.update_status("❌ Initialization Failed", "#F44336")
        threading.Thread(target=init_thread, daemon=True).start()
    
    def display_message(self, message: str, msg_type: str = "normal", replace_last: bool = False):
        """Displays messages with formatting."""
        def update_text():
            self.text_area.configure(state="normal")
            if replace_last and msg_type == "partial":
                content = self.text_area.get("1.0", tk.END)
                lines = content.split('\n')
                if len(lines) >= 2 and lines[-2].startswith('🗣️'):
                    self.text_area.delete(f"{len(lines)-2}.0", tk.END)
            
            start_pos = self.text_area.index(tk.INSERT)
            self.text_area.insert(tk.END, message)
            end_pos = self.text_area.index(tk.INSERT)
            if msg_type != "normal":
                self.text_area.tag_add(msg_type, start_pos, end_pos)
            
            self.chat_lines += message.count('\n')
            if self.chat_lines > self.max_chat_lines:
                lines_to_remove = self.chat_lines - self.max_chat_lines + 100
                self.text_area.delete("1.0", f"{lines_to_remove}.0")
                self.chat_lines = self.max_chat_lines - 100
            
            self.text_area.configure(state="disabled")
            self.text_area.see(tk.END)
        self.root.after(0, update_text)
    
    def update_status(self, status: str, color: str = "#58A6FF"):
        """Updates status with thread safety."""
        def update():
            self.status_var.set(status)
            self.status_label.configure(fg=color)
        self.root.after(0, update)
    
    def set_listening_state(self, is_listening: bool):
        """Updates UI for listening state."""
        def update():
            self.listening_animation = is_listening
            if is_listening:
                self.voice_button.configure(text="🔴 Listening...", state="disabled")
                self.emergency_button.configure(state="disabled")
            else:
                self.voice_button.configure(text="🎤 Voice Command", state="normal")
                self.emergency_button.configure(state="normal")
        self.root.after(0, update)
    
    def animate_interface(self):
        """Animates interface elements."""
        self.pulse_state = (self.pulse_state + 1) % 60
        if self.listening_animation:
            intensity = int(255 * (0.3 + 0.7 * abs(1 - (self.pulse_state % 10) / 5.0)))
            color = f"#{intensity:02x}5722"
        else:
            alpha = abs(30 - self.pulse_state) / 30.0
            intensity = int(100 + 155 * alpha)
            color = f"#{56:02x}{intensity:02x}{56:02x}"
        self.pulse_dot.configure(fg=color)
        self.root.after(50, self.animate_interface)
    
    def trigger_emergency_input(self):
        """Triggers emergency voice input."""
        if not self.assistant.manual_voice_input(emergency=True):
            messagebox.showwarning("Warning", "Cannot start emergency input - already processing or voice unavailable")
    
    def manual_voice_input(self):
        """Triggers manual voice input."""
        if not self.assistant.manual_voice_input(emergency=False):
            messagebox.showwarning("Warning", "Cannot start voice input - already processing or voice unavailable")
    
    def clear_chat(self):
        """Clears chat history."""
        if messagebox.askyesno("Clear Chat", "Are you sure you want to clear the chat history?"):
            self.text_area.configure(state="normal")
            self.text_area.delete("1.0", tk.END)
            self.text_area.configure(state="disabled")
            self.chat_lines = 0
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            welcome = f"[{timestamp}] Chat cleared. Survival Assistant is ready.\n"
            self.display_message(welcome, "system")
    
    def export_chat(self):
        """Exports chat log to file."""
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")], title="Export Chat Log")
            if filename:
                content = self.text_area.get("1.0", tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"Survival Assistant Chat Log\nExported: {datetime.datetime.now()}\n{'=' * 50}\n\n{content}")
                messagebox.showinfo("Export Complete", f"Chat log saved to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export chat log: {e}")
    
    def test_ai_connection(self):
        """Tests AI service connection."""
        def test_thread():
            self.update_status("🔄 Testing AI Connection", "#FFA657")
            if self.assistant.ai_interface.test_connection():
                response = self.assistant.ai_interface.generate_response("Test connection - respond with 'Connection successful'")
                if response:
                    self.update_status("✅ AI Connection OK", "#238636")
                    messagebox.showinfo("AI Test", "AI connection is working properly!")
                else:
                    self.update_status("⚠️ AI Response Issue", "#F44336")
                    messagebox.showwarning("AI Test", "AI connected but not responding properly")
            else:
                self.update_status("❌ AI Connection Failed", "#F44336")
                messagebox.showerror("AI Test", "Cannot connect to AI service. Check Ollama installation and configuration.")
            self.root.after(3000, lambda: self.update_status("🟢 Ready", "#2196F3"))
        threading.Thread(target=test_thread, daemon=True).start()
    
    def test_voice_input(self):
        """Tests voice input functionality."""
        if not VOSK_AVAILABLE:
            messagebox.showerror("Voice Test", "Voice recognition is not available. Please install Vosk and pyaudio.")
            return
        if not self.assistant.audio_manager.stream:
            messagebox.showerror("Voice Test", "Voice input is not initialized. Check microphone and Vosk model.")
            return
        
        def test_voice():
            self.display_message("🎤 Voice test starting - say something...\n", "system")
            result = self.assistant.audio_manager.listen(timeout=5)
            if result:
                self.display_message(f"✅ Voice test successful: '{result}'\n", "system")
                messagebox.showinfo("Voice Test", f"Voice recognition working!\nDetected: '{result}'")
            else:
                self.display_message("❌ Voice test failed - no input detected\n", "system")
                messagebox.showwarning("Voice Test", "No clear speech detected. Check microphone settings.")
        threading.Thread(target=test_voice, daemon=True).start()
    
    def show_settings(self):
        """Shows settings dialog."""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("600x500")
        settings_window.configure(bg="#0D1117")
        settings_window.resizable(False, False)
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        settings_window.update_idletasks()
        x = (settings_window.winfo_screenwidth() // 2) - (600 // 2)
        y = (settings_window.winfo_screenheight() // 2) - (500 // 2)
        settings_window.geometry(f"600x500+{x}+{y}")
        
        notebook = ttk.Notebook(settings_window)
        notebook.pack(fill="both", expand=True, padx=20, pady=20)
        
        ai_frame = ttk.Frame(notebook)
        notebook.add(ai_frame, text="AI Settings")
        ttk.Label(ai_frame, text="Ollama URL:").pack(anchor="w", pady=(10, 5))
        ai_url_var = tk.StringVar(value=self.assistant.config["ollama_url"])
        ttk.Entry(ai_frame, textvariable=ai_url_var, width=50).pack(fill="x", pady=(0, 10))
        ttk.Label(ai_frame, text="Model Name:").pack(anchor="w", pady=(10, 5))
        model_var = tk.StringVar(value=self.assistant.config["model_name"])
        ttk.Entry(ai_frame, textvariable=model_var, width=50).pack(fill="x", pady=(0, 10))
        
        voice_frame = ttk.Frame(notebook)
        notebook.add(voice_frame, text="Voice Settings")
        ttk.Label(voice_frame, text="Vosk Model Path:").pack(anchor="w", pady=(10, 5))
        vosk_var = tk.StringVar(value=self.assistant.config["vosk_model_path"])
        ttk.Entry(voice_frame, textvariable=vosk_var, width=50).pack(fill="x", pady=(0, 10))
        ttk.Label(voice_frame, text="Speech Rate:").pack(anchor="w", pady=(10, 5))
        rate_var = tk.IntVar(value=self.assistant.config["tts_settings"]["rate"])
        ttk.Scale(voice_frame, from_=100, to=300, variable=rate_var, orient="horizontal").pack(fill="x", pady=(0, 10))
        
        wake_frame = ttk.Frame(notebook)
        notebook.add(wake_frame, text="Wake Words")
        ttk.Label(wake_frame, text="Wake Words (one per line):").pack(anchor="w", pady=(10, 5))
        wake_text = tk.Text(wake_frame, height=8, width=50)
        wake_text.pack(fill="both", expand=True, pady=(0, 10))
        wake_text.insert("1.0", "\n".join(self.assistant.config["wake_words"]))
        
        button_frame = ttk.Frame(settings_window)
        button_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        def save_settings():
            try:
                new_config = self.assistant.config.copy()
                new_config["ollama_url"] = ai_url_var.get()
                new_config["model_name"] = model_var.get()
                new_config["vosk_model_path"] = vosk_var.get()
                new_config["tts_settings"]["rate"] = rate_var.get()
                new_config["wake_words"] = [line.strip() for line in wake_text.get("1.0", tk.END).split("\n") if line.strip()]
                ConfigManager.save_config(new_config)
                messagebox.showinfo("Settings", "Settings saved! Please restart the application for changes to take effect.")
                settings_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save settings: {e}")
        
        ttk.Button(button_frame, text="Save", command=save_settings).pack(side="right", padx=(10, 0))
        ttk.Button(button_frame, text="Cancel", command=settings_window.destroy).pack(side="right")
    
    def show_wake_words(self):
        """Shows wake words help."""
        wake_words = "\n".join([f"• {word}" for word in self.assistant.config["wake_words"]])
        messagebox.showinfo("Wake Words", f"Say any of these phrases to activate:\n\n{wake_words}\n\nFollowed by your emergency description.")
    
    def show_emergency_help(self):
        """Shows emergency commands help."""
        help_text = """Emergency Commands:

🚨 IMMEDIATE ACTIVATION:
• "Emergency" + description
• "Help" + situation  
• "Urgent" + problem

🎯 DIRECT QUESTIONS:
• "How do I..." 
• "What should I do if..."
• "Where can I find..."

⚡ QUICK ACCESS:
• Use Emergency Voice Input button
• Speak wake word then describe situation
• Voice commands are always active

💡 TIPS:
• Speak clearly and describe your situation
• Include location and available resources
• Be specific about immediate dangers"""
        messagebox.showinfo("Emergency Commands", help_text)
    
    def show_about(self):
        """Shows about dialog."""
        about_text = """Advanced Survival Assistant v2.0

An AI-powered emergency survival assistant with voice interaction capabilities.

Features:
• Real-time voice recognition
• Emergency-focused AI responses  
• Wake word activation
• Speech synthesis
• Offline operation (with local AI)

Requirements:
• Ollama with survival-focused model
• Vosk speech recognition model
• Working microphone and speakers

Created for emergency preparedness and survival situations."""
        messagebox.showinfo("About", about_text)
    
    def on_closing(self):
        """Handles window closing."""
        if messagebox.askokcancel("Quit", "Do you want to quit the Survival Assistant?"):
            self.quit_app()
    
    def quit_app(self):
        """Performs clean shutdown."""
        self.display_message("🔄 Shutting down survival assistant...\n", "system")
        def shutdown_thread():
            try:
                self.assistant.shutdown()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Shutdown error: {e}")
            finally:
                self.root.after(0, self.root.quit)
        threading.Thread(target=shutdown_thread, daemon=True).start()

### Utility Functions
def setup_signal_handlers():
    """Sets up signal handlers for clean shutdown."""
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal")
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def main():
    """Main application entry point."""
    setup_signal_handlers()
    
    root = tk.Tk()
    try:
        # Set application icon if available (commented out as optional)
        # root.iconbitmap("survival_assistant.ico")
        pass
    except:
        pass
    
    app = ModernAssistantGUI(root)
    
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (1000 // 2)
    y = (root.winfo_screenheight() // 2) - (800 // 2)
    root.geometry(f"1000x800+{x}+{y}")
    
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    startup_msg = f"""[{timestamp}] 🆘 SURVIVAL ASSISTANT v2.0 STARTED

✅ Enhanced Features:
• Improved voice recognition with live feedback
• Better AI response processing  
• Emergency priority handling
• Comprehensive error handling
• Settings management
• Chat export functionality

🎤 Voice Commands Active - Say wake words or direct emergency commands
🤖 AI Ready - Survival knowledge at your service
📋 Check Help menu for command reference

Stay safe and be prepared! 🛡️

"""
    app.display_message(startup_msg, "system")
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
    
    logger.info("Survival Assistant shutdown complete")

if __name__ == "__main__":
    main()