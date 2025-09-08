from backend.modules.summarizer import summarize_transcript

def generate_report(transcript_entries):
    return summarize_transcript(transcript_entries, output_file="outputs/report.json")
