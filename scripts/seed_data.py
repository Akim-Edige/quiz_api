"""
Seed script to create sample quiz data for testing the API.
Run this after database migrations to populate with example content.
"""

import asyncio
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models import (
    Quiz, QuizI18n, Question, QuestionI18n, 
    ChoiceOption, ChoiceOptionI18n, FillGap, FillGapAnswer,
    MatchingPair, MediaAsset, MediaAssetI18n,
    QuizStatus, QuestionType, SideKind
)
import hashlib
from pathlib import Path
from app.config import settings
from sqlalchemy import select, delete


async def create_sample_quiz():
    """Create a sample quiz with various question types"""
    
    async with AsyncSessionLocal() as session:
        # Create or reuse quiz
        existing_quiz = (await session.execute(
            select(Quiz).where(Quiz.slug == "general-knowledge-quiz")
        )).scalar_one_or_none()
        if existing_quiz:
            quiz_id = existing_quiz.id
        else:
            quiz_id = uuid.uuid4()
            quiz = Quiz(
                id=quiz_id,
                slug="general-knowledge-quiz",
                status=QuizStatus.PUBLISHED
            )
            session.add(quiz)
            
            # Add quiz i18n
            quiz_i18n_en = QuizI18n(
                quiz_id=quiz_id,
                locale="en",
                title="General Knowledge Quiz",
                description="Test your general knowledge with this comprehensive quiz covering various topics."
            )
            quiz_i18n_es = QuizI18n(
                quiz_id=quiz_id,
                locale="es",
                title="Quiz de Conocimientos Generales",
                description="Pon a prueba tus conocimientos generales con este quiz completo que cubre varios temas."
            )
            session.add_all([quiz_i18n_en, quiz_i18n_es])
        
        # Only create Q1-Q3 when creating a new quiz
        if not existing_quiz:
            # Question 1: Single Choice
            q1_id = uuid.uuid4()
            question1 = Question(
                id=q1_id,
                quiz_id=quiz_id,
                qtype=QuestionType.SINGLE_CHOICE,
                display_order=1,
                points=100,
                meta={"difficulty": "easy", "category": "geography"}
            )
            session.add(question1)
            
            # Question 1 i18n
            q1_i18n_en = QuestionI18n(
                question_id=q1_id,
                locale="en",
                prompt="What is the capital of France?",
                explanation="Paris is the capital and most populous city of France, located in the north-central part of the country."
            )
            q1_i18n_es = QuestionI18n(
                question_id=q1_id,
                locale="es",
                prompt="¿Cuál es la capital de Francia?",
                explanation="París es la capital y la ciudad más poblada de Francia, ubicada en la parte centro-norte del país."
            )
            session.add_all([q1_i18n_en, q1_i18n_es])
            
            # Question 1 options
            options_data = [
                ("London", "Londres", False),
                ("Paris", "París", True),
                ("Madrid", "Madrid", False),
                ("Rome", "Roma", False)
            ]
            
            for i, (label_en, label_es, is_correct) in enumerate(options_data):
                option_id = uuid.uuid4()
                option = ChoiceOption(
                    id=option_id,
                    question_id=q1_id,
                    display_order=i + 1,
                    is_correct=is_correct
                )
                session.add(option)
                
                option_i18n_en = ChoiceOptionI18n(
                    option_id=option_id,
                    locale="en",
                    label=label_en
                )
                option_i18n_es = ChoiceOptionI18n(
                    option_id=option_id,
                    locale="es", 
                    label=label_es
                )
                session.add_all([option_i18n_en, option_i18n_es])
            
            # Question 2: Multi Choice
            q2_id = uuid.uuid4()
            question2 = Question(
                id=q2_id,
                quiz_id=quiz_id,
                qtype=QuestionType.MULTI_CHOICE,
                display_order=2,
                points=100,
                meta={"difficulty": "medium", "category": "science"}
            )
            session.add(question2)
            
            q2_i18n_en = QuestionI18n(
                question_id=q2_id,
                locale="en",
                prompt="Which of the following are planets in our solar system? (Select all that apply)",
                explanation="Mars, Jupiter, and Venus are all planets in our solar system. The Sun is a star, not a planet."
            )
            q2_i18n_es = QuestionI18n(
                question_id=q2_id,
                locale="es",
                prompt="¿Cuáles de los siguientes son planetas de nuestro sistema solar? (Selecciona todos los que correspondan)",
                explanation="Marte, Júpiter y Venus son todos planetas de nuestro sistema solar. El Sol es una estrella, no un planeta."
            )
            session.add_all([q2_i18n_en, q2_i18n_es])
            
            # Question 2 options
            multi_options_data = [
                ("Mars", "Marte", True),
                ("Jupiter", "Júpiter", True),
                ("The Sun", "El Sol", False),
                ("Venus", "Venus", True)
            ]
            
            for i, (label_en, label_es, is_correct) in enumerate(multi_options_data):
                option_id = uuid.uuid4()
                option = ChoiceOption(
                    id=option_id,
                    question_id=q2_id,
                    display_order=i + 1,
                    is_correct=is_correct
                )
                session.add(option)
                
                option_i18n_en = ChoiceOptionI18n(
                    option_id=option_id,
                    locale="en",
                    label=label_en
                )
                option_i18n_es = ChoiceOptionI18n(
                    option_id=option_id,
                    locale="es",
                    label=label_es
                )
                session.add_all([option_i18n_en, option_i18n_es])
            
            # Question 3: Fill in the Gap
            q3_id = uuid.uuid4()
            question3 = Question(
                id=q3_id,
                quiz_id=quiz_id,
                qtype=QuestionType.FILL_GAP,
                display_order=3,
                points=100,
                meta={"difficulty": "medium", "category": "history"}
            )
            session.add(question3)
            
            q3_i18n_en = QuestionI18n(
                question_id=q3_id,
                locale="en",
                prompt="The _____ War ended in 1945.",
                explanation="World War II (also known as the Second World War) ended in 1945."
            )
            q3_i18n_es = QuestionI18n(
                question_id=q3_id,
                locale="es",
                prompt="La _____ Guerra Mundial terminó en 1945.",
                explanation="La Segunda Guerra Mundial terminó en 1945."
            )
            session.add_all([q3_i18n_en, q3_i18n_es])
            
            # Fill gap
            gap_id = uuid.uuid4()
            gap = FillGap(
                id=gap_id,
                question_id=q3_id,
                gap_index=0,
                case_sensitive=False
            )
            session.add(gap)
            
            # Accepted answers
            accepted_answers = ["Second", "second", "2nd", "World", "world"]
            for answer in accepted_answers:
                gap_answer = FillGapAnswer(
                    id=uuid.uuid4(),
                    gap_id=gap_id,
                    accepted_value=answer
                )
                session.add(gap_answer)
        
        # Question 4: Matching (use flag images on left, capitals on right)
        existing_q4 = (await session.execute(
            select(Question).where(Question.quiz_id == quiz_id, Question.display_order == 4)
        )).scalar_one_or_none()
        if existing_q4:
            q4_id = existing_q4.id
            # Ensure type/points/meta
            existing_q4.qtype = QuestionType.MATCHING
            existing_q4.points = 100
            existing_q4.meta = {"difficulty": "easy", "category": "geography"}
            question4 = existing_q4
        else:
            q4_id = uuid.uuid4()
            question4 = Question(
                id=q4_id,
                quiz_id=quiz_id,
                qtype=QuestionType.MATCHING,
                display_order=4,
                points=100,
                meta={"difficulty": "easy", "category": "geography"}
            )
            session.add(question4)
        
        # Upsert q4 i18n entries
        existing_en = (await session.execute(
            select(QuestionI18n).where(QuestionI18n.question_id == q4_id, QuestionI18n.locale == "en")
        )).scalar_one_or_none()
        if not existing_en:
            session.add(QuestionI18n(
                question_id=q4_id,
                locale="en",
                prompt="Match each country with its capital city.",
                explanation="These are the correct capital cities for each country."
            ))
        existing_es = (await session.execute(
            select(QuestionI18n).where(QuestionI18n.question_id == q4_id, QuestionI18n.locale == "es")
        )).scalar_one_or_none()
        if not existing_es:
            session.add(QuestionI18n(
                question_id=q4_id,
                locale="es",
                prompt="Empareja cada país con su ciudad capital.",
                explanation="Estas son las ciudades capitales correctas para cada país."
            ))
        
        # Prepare media assets for flags (reuse by s3_key or create)
        assets_dir = Path(__file__).resolve().parent.parent / "app" / "assets" / "matching_images"
        flag_files = {
            "Italy": "italy_flag.png",
            "Japan": "japan_flag.png",
            "Brazil": "brazil_flag.png",
            "Germany": "germany_flag.png",
        }
        flag_assets: dict[str, uuid.UUID] = {}
        for country, filename in flag_files.items():
            s3_key = f"matching_images/{filename}"
            existing_asset = (await session.execute(
                select(MediaAsset).where(MediaAsset.s3_bucket == settings.s3_bucket, MediaAsset.s3_key == s3_key)
            )).scalar_one_or_none()
            if existing_asset:
                asset_id = existing_asset.id
                # Ensure i18n exists
                for loc, alt in [("en", f"Flag of {country}"), ("es", f"Bandera de {country}")]:
                    exists_i18n = (await session.execute(
                        select(MediaAssetI18n).where(MediaAssetI18n.asset_id == asset_id, MediaAssetI18n.locale == loc)
                    )).scalar_one_or_none()
                    if not exists_i18n:
                        session.add(MediaAssetI18n(asset_id=asset_id, locale=loc, alt_text=alt))
            else:
                file_path = assets_dir / filename
                with open(file_path, "rb") as f:
                    data = f.read()
                digest = hashlib.sha256(data).digest()
                asset_id = uuid.uuid4()
                asset = MediaAsset(
                    id=asset_id,
                    s3_bucket=settings.s3_bucket,
                    s3_key=s3_key,
                    mime="image/png",
                    sha256=digest,
                    width=None,
                    height=None,
                )
                session.add(asset)
                # Alt text in English and Spanish
                session.add_all([
                    MediaAssetI18n(asset_id=asset_id, locale="en", alt_text=f"Flag of {country}"),
                    MediaAssetI18n(asset_id=asset_id, locale="es", alt_text=f"Bandera de {country}"),
                ])
            flag_assets[country] = asset_id
        
        # Replace matching pairs for Q4
        await session.execute(delete(MatchingPair).where(MatchingPair.question_id == q4_id))
        matching_data = [
            ("Italy", "Rome"),
            ("Japan", "Tokyo"),
            ("Brazil", "Brasília"),
            ("Germany", "Berlin")
        ]
        for country, right_text in matching_data:
            pair = MatchingPair(
                id=uuid.uuid4(),
                question_id=q4_id,
                left_kind=SideKind.IMAGE,
                left_asset_id=flag_assets[country],
                right_kind=SideKind.TEXT,
                right_text=right_text
            )
            session.add(pair)
        
        await session.commit()
        print(f"✅ Seeded/updated quiz with ID: {quiz_id}")
        return quiz_id


async def create_sample_media_asset():
    """Create a sample media asset for testing"""
    async with AsyncSessionLocal() as session:
        bucket = settings.s3_bucket
        s3_key = "samples/eiffel-tower.jpg"
        existing = (await session.execute(
            select(MediaAsset).where(MediaAsset.s3_bucket == bucket, MediaAsset.s3_key == s3_key)
        )).scalar_one_or_none()
        if existing:
            # Ensure alt-text entries exist
            for loc, alt in [("en", "The Eiffel Tower in Paris, France"), ("es", "La Torre Eiffel en París, Francia")]:
                exists_i18n = (await session.execute(
                    select(MediaAssetI18n).where(MediaAssetI18n.asset_id == existing.id, MediaAssetI18n.locale == loc)
                )).scalar_one_or_none()
                if not exists_i18n:
                    session.add(MediaAssetI18n(asset_id=existing.id, locale=loc, alt_text=alt))
            await session.commit()
            print(f"ℹ️ Sample media asset already exists with ID: {existing.id}")
            return existing.id
        
        asset_id = uuid.uuid4()
        asset = MediaAsset(
            id=asset_id,
            s3_bucket=bucket,
            s3_key=s3_key,
            mime="image/jpeg",
            sha256=b"sample_hash_bytes_here",
            width=800,
            height=600
        )
        session.add(asset)
        
        # Add i18n for alt text
        session.add_all([
            MediaAssetI18n(asset_id=asset_id, locale="en", alt_text="The Eiffel Tower in Paris, France"),
            MediaAssetI18n(asset_id=asset_id, locale="es", alt_text="La Torre Eiffel en París, Francia"),
        ])
        
        await session.commit()
        print(f"✅ Created sample media asset with ID: {asset_id}")
        return asset_id


async def main():
    """Main seeding function"""
    print("🌱 Seeding sample data...")
    
    try:
        quiz_id = await create_sample_quiz()
        asset_id = await create_sample_media_asset()
        
        print(f"\n🎉 Seeding completed successfully!")
        print(f"📝 Sample Quiz ID: {quiz_id}")
        print(f"🖼️  Sample Asset ID: {asset_id}")
        print(f"\n🔗 Test the API:")
        print(f"   GET http://localhost:8000/api/quizzes/{quiz_id}?locale=en")
        print(f"   GET http://localhost:8000/api/quizzes/{quiz_id}?locale=es")
        print(f"   GET http://localhost:8000/api/quizzes/{quiz_id}/stats")
        
    except Exception as e:
        print(f"❌ Error seeding data: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main()) 