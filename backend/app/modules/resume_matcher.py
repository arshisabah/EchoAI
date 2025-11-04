# backend/modules/resume_matcher.py

# 1. Import the loader and similarity function
from app.models.embedding.loader import load_embedding_model
from sklearn.metrics.pairwise import cosine_similarity

# 2. Load the embedding model
print("Initializing resume matcher module...")
embedding_model = load_embedding_model()

def match_resumes(text1: str, text2: str):
    """
    Calculates the semantic similarity between two texts and returns a match score.

    This is used to compare a job description against a candidate's response or resume.

    Args:
        text1 (str): The first text (e.g., job description).
        text2 (str): The second text (e.g., candidate's answer).

    Returns:
        str: A formatted string indicating the match percentage (e.g., "85.72% match").
    """
    if not embedding_model:
        return "Error: Embedding model not loaded."

    try:
        # 3. Convert both texts into numerical vectors (embeddings)
        embeddings = embedding_model.encode([text1, text2])

        # 4. Calculate the cosine similarity between the two vectors
        # The result is a matrix, so we access the score at [0, 0]
        similarity_score = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]

        # 5. Format the score as a percentage
        match_percentage = similarity_score * 100
        return f"{match_percentage:.2f}% match"

    except Exception as e:
        print(f"❌ An error occurred during resume matching: {e}")
        return f"Error: {e}"

if __name__ == '__main__':
    job_requirement = "Seeking a software engineer with strong Python skills and experience in developing RESTful APIs."
    
    candidate_answer_good = "I am a software developer with over 5 years of experience in Python. My main focus has been building scalable REST APIs for various web applications."
    
    candidate_answer_bad = "I am a project manager skilled in agile methodologies and leading teams."

    print("\n--- Resume Matching Results ---")
    
    match_result_1 = match_resumes(job_requirement, candidate_answer_good)
    print(f"\nComparing Requirement to GOOD Candidate Answer:")
    print(f"Result: {match_result_1}")
    
    match_result_2 = match_resumes(job_requirement, candidate_answer_bad)
    print(f"\nComparing Requirement to BAD Candidate Answer:")
    print(f"Result: {match_result_2}")

    print("\nResume matcher module is ready.")