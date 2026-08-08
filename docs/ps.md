Agentic Financial Operations Assistant

HOW THIS TRACK GETS SCORED
Dimension	Weight
Business Impact	20%
AI Innovation & Depth	20%
Technical Excellence	20%
Enterprise Architecture & Integration	15%
User Experience	10%
Scalability, Security & Cost	10%
Presentation	5%

THE PROBLEM
Financial operations teams handle customer support, payments, fraud investigations, and internal process requests — each usually living in a different system, each needing someone to look up context, decide the right action, and carry it out by hand. That manual orchestration across systems slows down routine work and eats time that should go to the cases that genuinely need human judgment.
YOUR MISSION
Build an AI agent capable of autonomously handling operational tasks across customer support, payments, fraud investigations, and internal operations by orchestrating and reasoning across multiple enterprise systems — while keeping humans in the approval loop for high-risk actions.

WHAT YOU'LL WORK WITH — AND THE RULES THAT COME WITH IT
DATA YOUR SOLUTION SHOULD USE
•	Customer support tickets and chat/call transcripts
•	Payment transaction logs and dispute/failure records
•	Fraud case history and investigation notes
•	Internal ops workflows and approval records
•	Access to enterprise systems (CRM, payments platform, case management)		GUARDRAILS YOU MUST RESPECT
•	Human-in-the-Loop: any high-risk or irreversible action (refunds above a threshold, account actions, fraud holds) must go through human approval before it executes.
•	Auditability: every autonomous action, and every decision to escalate instead of act, must be logged with a clear, plain-language reason.
•	Data Privacy: handle customer financial and personal data in line with applicable Indian data protection and RBI guidance.
•	Explainability: the agent must be able to explain, in plain language, why it took — or recommended — a given action.
GENERAL BUILD PRINCIPLES (APPLIES TO EVERY TRACK)
•	Prefer several specialized, cooperating agents over one giant mega-prompt.
•	Use cheap/fast models for routine decisions and save expensive reasoning for the high-stakes ones — report a rough cost-per-decision.
•	Where practical, show that a smaller open-source model, RAG, or a classical solver could replace constant calls to an expensive commercial LLM.
•	Add a self-check step: have the system review its own output against the Business Goals before it's final.
WHAT TO DELIVER
•	A working MVP demonstrating the full user journey for this track
•	A short tech write-up: architecture diagram, AI workflow, and stack used
•	Source code in a GitHub repo with setup instructions
•	A short business pitch: problem, solution, value, rough cost-per-transaction, what's next
•	A live demo (max 8 minutes): the problem, your solution, a walkthrough, your AI architecture, impact & roadmap
