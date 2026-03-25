-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.Chat_History (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  user_id uuid DEFAULT auth.uid(),
  sender text,
  message text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT Chat_History_pkey PRIMARY KEY (id),
  CONSTRAINT Chat_History_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.Profiles(id)
);
CREATE TABLE public.Courses_DB (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  university_name text,
  course_name text,
  location text,
  career_category text,
  website_link text,
  college_type text DEFAULT 'local'::text,
  CONSTRAINT Courses_DB_pkey PRIMARY KEY (id)
);
CREATE TABLE public.Profiles (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  full_name text NOT NULL,
  grade_level text,
  created_at timestamp without time zone DEFAULT now(),
  gender text,
  profile_url text,
  role text DEFAULT 'user'::text,
  last_active_at timestamp with time zone,
  CONSTRAINT Profiles_pkey PRIMARY KEY (id),
  CONSTRAINT Profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);
CREATE TABLE public.Reports (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  user_id uuid DEFAULT auth.uid(),
  career_prediction text,
  matching_factor text,
  pdf_url text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  roadmap jsonb,
  CONSTRAINT Reports_pkey PRIMARY KEY (id),
  CONSTRAINT Reports_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.Profiles(id)
);
CREATE TABLE public.User_Features (
  user_id uuid NOT NULL,
  city_type text,
  family_income text,
  plus2_stream text,
  plus2_gpa numeric,
  grade_english text,
  grade_nepali text,
  grade_social text,
  grade_math text,
  grade_physics text,
  grade_chemistry text,
  grade_biology text,
  grade_computer text,
  grade_accounts text,
  grade_economics text,
  grade_law text,
  interest_technology integer DEFAULT 0,
  interest_math_stats integer DEFAULT 0,
  interest_art_design integer DEFAULT 0,
  interest_business_money integer DEFAULT 0,
  interest_social_people integer DEFAULT 0,
  interest_bio_health integer DEFAULT 0,
  interest_nature_agri integer DEFAULT 0,
  interest_construction integer DEFAULT 0,
  interest_law_politics integer DEFAULT 0,
  interest_hospitality_food integer DEFAULT 0,
  interest_gaming_entertainment integer DEFAULT 0,
  interest_history_culture integer DEFAULT 0,
  score_ioe numeric DEFAULT 0,
  score_cee numeric DEFAULT 0,
  score_cmat numeric DEFAULT 0,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT User_Features_pkey PRIMARY KEY (user_id),
  CONSTRAINT User_Features_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.Profiles(id)
);