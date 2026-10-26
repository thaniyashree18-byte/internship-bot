"""Gemini-powered content generation with deterministic demo fallbacks."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from data import log_action

load_dotenv()


def generate_text(prompt: str, fallback: str, action: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        log_action(action, "fallback", "GEMINI_API_KEY is not configured; used template.")
        return fallback
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        text = getattr(response, "text", "").strip()
        if not text:
            raise ValueError("Gemini returned an empty response.")
        log_action(action, "success", "Content generated with Gemini.")
        return text
    except Exception as exc:
        log_action(action, "fallback", f"Gemini unavailable ({type(exc).__name__}); used template.")
        return fallback


def create_welcome(intern: dict[str, object]) -> str:
    fallback = (
        f"Hi {intern.get('Name', 'there')},\n\n"
        f"Welcome to the {intern.get('Track', '')} internship! Your joining date is "
        f"{intern.get('Join_Date', 'to be confirmed')}.\n\n"
        f"Your project is {intern.get('Task_Title', 'your assigned project')}: "
        f"{intern.get('Task_Description', '')}\n\n"
        f"Build these modules: {intern.get('Modules', '')}.\n"
        f"Include these features: {intern.get('Features', '')}.\n"
        f"Suggested technology: {intern.get('Tech_Stack', '')}.\n\n"
        "Submit your work in a public GitHub repository and share your GitHub username "
        "before your review. Please do not include passwords, API keys, or personal data "
        "in your repository."
    )
    prompt = (
        "Write a concise, warm and professional internship welcome email using only these facts. "
        "Do not invent dates or promises. Include joining date, task, modules, features, tech stack, "
        "and instructions to submit via a public GitHub repository.\n\n"
        f"Intern details: {intern}"
    )
    return generate_text(prompt, fallback, "welcome_content")


def create_orientation(intern: dict[str, object]) -> str:
    fallback = (
        f"Hi {intern.get('Name', 'there')},\n\n"
        f"Your project is {intern.get('Task_Title', '')}. {intern.get('Task_Description', '')}\n\n"
        f"Suggested tools: {intern.get('Tech_Stack', '')}.\n"
        f"Work through these modules: {intern.get('Modules', '')}.\n"
        f"Add these features: {intern.get('Features', '')}.\n\n"
        f"Completion criteria: implement and test every listed module and feature, add a README "
        f"with setup and usage instructions, and submit the repository before "
        f"{intern.get('End_Date', 'the agreed deadline')}. Keep your commits focused and share "
        "your GitHub username for review."
    )
    prompt = (
        "Explain this internship project top-to-bottom as a practical orientation email. "
        "Use sections for what to build, suggested steps, tools, modules, features, completion "
        "criteria, GitHub submission, and deadline. Do not add unsupported requirements.\n\n"
        f"Intern details: {intern}"
    )
    return generate_text(prompt, fallback, "orientation_content")


def create_review(intern: dict[str, object], repository_report: str, review_number: int) -> str:
    fallback = (
        f"Review {review_number} for {intern.get('Name', 'intern')}\n\n"
        "What went well: Your submission was reviewed and provides a starting point for the "
        "assigned project.\n\n"
        "What to improve: Add clear setup instructions, tests, and evidence for each required "
        "feature. Verify the project runs from a clean checkout.\n\n"
        f"Missing modules/features to verify: {intern.get('Modules', '')}; "
        f"{intern.get('Features', '')}.\n\n"
        "Score: 5/10 (provisional; repository details could not be evaluated reliably).\n\n"
        "Next-review goals: Complete the remaining modules, update the README, and make a focused "
        "commit documenting your progress."
    )
    prompt = (
        "Review this intern's public project fairly and constructively. Respond with sections: "
        "What was done well, What to improve, Missing modules/features, Score: N/10, and "
        "Next-review goals. Do not claim that unobserved features exist. If evidence is incomplete, "
        "say so and score cautiously. Avoid exposing secrets or personal data.\n\n"
        f"Project task: {intern.get('Task_Title')}\n"
        f"Required modules: {intern.get('Modules')}\n"
        f"Required features: {intern.get('Features')}\n"
        f"Repository evidence:\n{repository_report[:14000]}"
    )
    return generate_text(prompt, fallback, f"review_{review_number}_content")
