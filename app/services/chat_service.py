import os
from google.genai import types
from supabase import create_client, ClientOptions
from app.database import supabase as global_supabase, url, key
from app.services.gemini_pool import gemini_pool
from app.chat_upload_meta import parse_upload_message

class ChatService:
    def __init__(self):
        # Gemini Client is now handled by gemini_pool
        self.prompt_path = os.path.join("app", "prompts", "system_prompt.txt")
        self.default_prompt = "You are a helpful career counselor."

    def _load_system_prompt(self):
        """Read system prompt from disk on every call so edits are live."""
        try:
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            print("System prompt file not found, using default.")
            return self.default_prompt

    async def get_career_advice(self, user_message: str, user_token: str) -> str:
        """Non-streaming version for backward compatibility or simple calls."""
        full_text = ""
        async for chunk in self.stream_career_advice(user_message, user_token):
            full_text += chunk
        return full_text

    async def stream_career_advice(
        self,
        user_message: str,
        user_token: str,
        ocr_text: str | None = None,
        user_message_for_db: str | None = None,
    ):
        """
        1. Validate Token
        2. Create Authenticated DB Connection (for RLS)
        3. Build Context
        4. Stream AI Response using GeminiPool
        5. Save History after completion
        """
        clean_user_message = (user_message or "").strip()
        clean_ocr_text = (ocr_text or "").strip()

        if not clean_user_message and not clean_ocr_text:
            yield "Please type a message or upload a document image."
            return

        # Live-load the system prompt from disk
        system_prompt = self._load_system_prompt()
        if clean_ocr_text:
            system_prompt += (
                "\n\nOCR MODE (HIGH PRIORITY): "
                "When OCR_CONTEXT is present, prioritize extracting +2 GPA and subject scores/grades. "
                "Respond in plain text only and never output JSON or code blocks for that OCR reply. "
                "If values are missing, list missing fields and ask one short follow-up question."
            )
        
        # --- Authentication ---
        user_id = None
        db_client = None

        try:
            user_response = global_supabase.auth.get_user(user_token)
            if not user_response or not user_response.user:
                yield "Authentication failed. Please login again."
                return
            
            user_id = user_response.user.id
            db_client = create_client(
                url, 
                key, 
                options=ClientOptions(headers={"Authorization": f"Bearer {user_token}"})
            )

        except Exception as e:
            print(f"Auth Error in Service: {str(e)}")
            yield "Authentication failed. Please login again."
            return

        # --- Context Building ---
        chat_history = self._build_history(db_client, user_id)
        
        # --- AI Generation (Streaming through the Pool) ---
        ai_response_text = ""
        
        try:
            final_user_prompt = clean_user_message

            if clean_ocr_text:
                ocr_instruction = (
                    "OCR_CONTEXT:\n"
                    f"{clean_ocr_text}\n\n"
                    "Task: Extract the student's +2 GPA and subject grades/scores if present.\n"
                    "Subjects to check: English, Nepali, Social, Math, Physics, Chemistry, Biology, "
                    "Computer, Accounts, Economics, Law.\n"
                    "For missing values, mark as 'Missing' and ask one concise follow-up question.\n"
                    "Reply in plain text only."
                )

                if clean_user_message:
                    final_user_prompt = f"{clean_user_message}\n\n{ocr_instruction}"
                else:
                    final_user_prompt = (
                        "Please analyze the uploaded academic document and extract GPA and subject scores.\n\n"
                        f"{ocr_instruction}"
                    )

            # Prepare the prompt contents
            prompt_with_context = chat_history + [types.Content(role="user", parts=[types.Part(text=final_user_prompt)])]
            
            # Use gemini_pool for robust rotation and fallback
            response_stream = gemini_pool.generate_content_stream(
                prompt=prompt_with_context,
                system_instruction=system_prompt
            )
            
            async for chunk in response_stream:
                if chunk.text:
                    ai_response_text += chunk.text
                    yield chunk.text
            
        except Exception as e:
            print(f"Gemini Pool exhaustion error: {e}")
            yield "I am currently overloaded. Please try again later."
            return

        # --- Save to Database (background) ---
        if ai_response_text:
            db_user_message = user_message_for_db if user_message_for_db is not None else clean_user_message
            if not db_user_message and clean_ocr_text:
                db_user_message = "Uploaded an image for OCR analysis."

            self._save_to_db(db_client, user_id, "user", db_user_message)
            self._save_to_db(db_client, user_id, "ai", ai_response_text)

    def _build_history(self, client, user_id: str):
        """Fetches Profile + Features + Last 20 messages using the authenticated client."""
        formatted_history = []

        try:
            # 1. Fetch Profile (Respects RLS: Users can only see their own)
            profile = client.table("Profiles").select("*").eq("id", user_id).single().execute()
            data = profile.data
            
            context_msg = (
                f"CONTEXT: User: {data.get('full_name')}. "
                f"Grade: {data.get('grade_level')}. "
                f"Gender: {data.get('gender')}."
            )
            
            # Fetch User Features if they exist
            try:
                features_res = client.table("User_Features").select("*").eq("user_id", user_id).maybe_single().execute()
                if features_res.data:
                    f_data = features_res.data
                    
                    # Helper blocks for formatting arrays of strings
                    grades_str = ", ".join([f"{k.replace('grade_', '')}: {v}" for k, v in f_data.items() if k.startswith('grade_') and v])
                    interests_str = ", ".join([f"{k.replace('interest_', '')}: {v}" for k, v in f_data.items() if k.startswith('interest_') and v is not None])
                    scores_str = ", ".join([f"{k.replace('score_', '').upper()}: {v}" for k, v in f_data.items() if k.startswith('score_') and v])

                    features_context = (
                        f" This user has already provided additional profile information. "
                        f"City Type: {f_data.get('city_type')}, Family Income: {f_data.get('family_income')}, "
                        f"Stream: {f_data.get('plus2_stream')}, GPA: {f_data.get('plus2_gpa')}. "
                        f"Grades: [{grades_str}]. "
                        f"Interests (0-10): [{interests_str}]. "
                        f"Entrance Scores: [{scores_str}]. "
                        "DO NOT ask the user for this information again unless they want to update it."
                    )
                    context_msg += features_context
            except Exception as f_e:
                print(f"Features Fetch Error: {f_e}")

            # 2. Fetch Latest Career Reports (Context of previous generations)
            try:
                reports_res = client.table("Reports")\
                    .select("career_prediction, matching_factor, created_at")\
                    .eq("user_id", user_id)\
                    .order("created_at", desc=True)\
                    .limit(3)\
                    .execute()
                
                if reports_res.data:
                    reports_context = "\nPREVIOUS CAREER REPORTS GENERATED:"
                    for r in reports_res.data:
                        pred = r.get("career_prediction", "Unknown")
                        # Parse matching factors if they are JSON
                        raw_factors = r.get("matching_factor", "[]")
                        try:
                            import json
                            factors_list = json.loads(raw_factors) if isinstance(raw_factors, str) else raw_factors
                            factors_text = "; ".join(factors_list) if isinstance(factors_list, list) else str(factors_list)
                        except:
                            factors_text = str(raw_factors)
                            
                        reports_context += f"\n- Recommended: {pred}. Logic: {factors_text}"
                    
                    context_msg += reports_context + "\nUse this context to provide consistent advice. If the user asks 'What should I do?', reference these recommendations."
            except Exception as r_e:
                print(f"Reports Context Fetch Error: {r_e}")
            
            formatted_history.append(types.Content(role="user", parts=[types.Part(text=context_msg)]))
            formatted_history.append(types.Content(role="model", parts=[types.Part(text="Understood. I have the user's profile, features, and previous career reports. I am ready to provide personalized guidance.")]))
            
        except Exception as e:
            print(f"Profile Fetch Error: {e}")
            # Continue without profile if it fails

        try:
            # 2. Fetch Chat History
            rows = client.table("Chat_History")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(50)\
                .execute()
            
            # Reverse to chronological order
            past_messages = rows.data[::-1]

            for msg in past_messages:
                role = "user" if msg['sender'] == "user" else "model"
                message_text = msg.get("message", "")

                if role == "user":
                    upload_meta, clean_text = parse_upload_message(message_text)
                    if upload_meta is not None:
                        # Keep OCR/image context in history without leaking metadata marker syntax.
                        message_text = clean_text or "User uploaded an academic image."

                if message_text:
                    formatted_history.append(types.Content(role=role, parts=[types.Part(text=message_text)]))
                
        except Exception as e:
            print(f"History Fetch Error: {e}")

        return formatted_history

    def _save_to_db(self, client, user_id: str, sender: str, text: str):
        try:
            client.table("Chat_History").insert({
                "user_id": user_id,
                "sender": sender,
                "message": text
            }).execute()
        except Exception as e:
            print(f"Save DB Error: {e}")

