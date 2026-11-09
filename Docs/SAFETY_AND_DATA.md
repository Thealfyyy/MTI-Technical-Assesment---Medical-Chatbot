# Safety, Grounding, and Data Privacy Rules

1. **Approved Corpus Boundary**: Only the nine supplied starter documents (`KB-01` through `KB-09` in `Docs/Data/`) may be used as medical knowledge sources. No external medical APIs, web searches, or unverified model pretraining facts may be surfaced as answers.
2. **Strict Abstention (`out_of_scope`)**: Any question unrelated to the corpus or asking for medical facts not explicitly supported by the retrieved chunks must return `status: "out_of_scope"` and `citations: []`.
3. **Clinical Safety & Escalation (`escalated`)**:
   - The chatbot must **never** provide a clinical diagnosis, patient-specific dosage recommendation, or treatment advice not explicitly written in the documents.
   - Questions asking for specific adult/pediatric dosing not in the documents (e.g., *"How many mg of Voltaren can an adult take per day?"*) or presenting urgent/emergency clinical red flags (e.g., severe dyspnea and cyanosis: *"عيان عنده ضيق نفس شديد وشفايفه زرقا، أديله Ventolin؟"*) must return `status: "escalated"` with `citations: []` and safe, non-advisory next-step guidance.
4. **Zero Real Patient Data**: All development, evaluation, analytics, and escalation handoff records must use the public assessment questions or synthetic test fixtures only.
5. **No Hardcoded Dev Answers**: The 10 public dev questions are used strictly as evaluation regression cases; application code must never pattern-match or branch on literal public question strings.
