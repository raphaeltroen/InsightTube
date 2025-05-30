import google.generativeai as genai
import google.auth


class Gemini:
    """
    Simple Gemini API client - use as a black box
    Just call init_model() with your preferred model and use ask()
    """

    _SERVICE_ACCOUNT_FILE_PATH = "secrets/hackathon-team-76_gen-lang-client-0325865525_iam_gserviceaccount_com_1747759055.json"

    # Available models with descriptions
    AVAILABLE_MODELS = {
        "gemini-1.5-flash": "Fast and versatile (recommended for beginners)",
        "gemini-1.5-pro": "Complex reasoning tasks (more powerful)",
        "gemini-2.0-flash": "Newest multimodal, fastest",
        "gemini-2.0-flash-lite": "Most cost-efficient",
        "gemini-2.5-flash-preview-05-20": "Best price-performance with thinking capabilities",
        "gemini-2.5-pro-preview-05-06": "Most powerful thinking model (advanced reasoning)"
    }

    def __init__(self):
        self.model = None
        self.chat = None
        self.model_name = None
        self._initialized = False

    def init_model(self, model_name=None):
        """
        Initialize Gemini model - call this once before using ask()
        
        Args:
            model_name (str, optional): Model to use. If None, shows selection menu.
            
        Returns:
            Gemini: Ready-to-use Gemini instance
            
        Raises:
            Exception: If initialization fails
        """
        try:
            # If no model specified, let user choose
            if model_name is None:
                model_name = self._select_model()

            # Validate model
            if model_name not in self.AVAILABLE_MODELS:
                raise ValueError(f"Invalid model. Available: {list(self.AVAILABLE_MODELS.keys())}")

            print(f"🚀 Initializing model: {model_name}...")

            # Configure Google AI API
            if not self._SERVICE_ACCOUNT_FILE_PATH:
                raise ValueError("Service account file path is not set. Please set Gemini._SERVICE_ACCOUNT_FILE_PATH or ensure it has a default value.")

            try:
                credentials, _ = google.auth.load_credentials_from_file(self._SERVICE_ACCOUNT_FILE_PATH)
            except FileNotFoundError:
                raise FileNotFoundError(f"Service account file not found at: {self._SERVICE_ACCOUNT_FILE_PATH}. Please check the path.")
            except Exception as e:
                raise Exception(f"Failed to load credentials from {self._SERVICE_ACCOUNT_FILE_PATH}: {e}")

            genai.configure(credentials=credentials)

            # Create model and chat session
            self.model = genai.GenerativeModel(model_name)
            self.chat = self.model.start_chat()
            self.model_name = model_name
            self._initialized = True

            print(f"✅ Gemini {model_name} is ready!")
            return self

        except Exception as e:
            raise Exception(f"Failed to initialize Gemini: {e}")

    def ask(self, question, short_answer=True):
        """
        Ask Gemini a question and get a response
        
        Args:
            question (str): The question to ask
            short_answer (bool): Whether to request a concise answer
            
        Returns:
            str: Gemini's response
            
        Raises:
            Exception: If not initialized or API error occurs
        """
        if not self._initialized:
            raise Exception("Model not initialized. Call init_model() first!")

        if not question or not question.strip():
            raise ValueError("Question cannot be empty")

        try:
            # Prepare prompt
            if short_answer:
                prompt = f"{question}\n\nPlease provide a short, concise answer with minimal explanation."
            else:
                prompt = question

            # Get response
            response = self.chat.send_message(prompt)
            return response.text

        except Exception as e:
            raise Exception(f"Error getting response: {e}")

    def get_model_name(self):
        """Get the current model name"""
        return self.model_name if self._initialized else None

    def get_available_models(self):
        """Get list of available models with descriptions"""
        return self.AVAILABLE_MODELS.copy()

    # ========== PRIVATE METHODS (HIDDEN FROM STUDENTS) ==========

    def _select_model(self):
        """Interactive model selection (hidden implementation)"""
        print("📋 Available Gemini Models:")
        print("=" * 50)

        models = list(self.AVAILABLE_MODELS.keys())
        for i, model in enumerate(models, 1):
            description = self.AVAILABLE_MODELS[model]
            print(f"{i}. {model}")
            print(f"   {description}\n")

        while True:
            try:
                choice = input(f"🔢 Select model (1-{len(models)}) or press Enter for default [1]: ").strip()

                if not choice:  # Default to gemini-1.5-flash (beginner-friendly)
                    selected = models[0]  # gemini-1.5-flash
                    print(f"✅ Using default model: {selected}")
                    return selected

                index = int(choice) - 1
                if 0 <= index < len(models):
                    selected = models[index]
                    print(f"✅ Selected model: {selected}")
                    return selected
                else:
                    print(f"⚠️ Invalid choice. Please enter 1-{len(models)}")

            except ValueError:
                print("⚠️ Invalid input. Please enter a number")
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                exit(0)


def init_model(model_name=None):
    """
    Convenience function to create and initialize a Gemini instance
    
    Args:
        model_name (str, optional): Model to use. If None, shows selection menu.
        
    Returns:
        Gemini: Ready-to-use Gemini instance
    """
    gemini = Gemini()
    return gemini.init_model(model_name)
