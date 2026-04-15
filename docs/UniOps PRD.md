# UniOps PRD

* **Product Requirements Document**  
* **Version:** 1.1 (28-Hour Hackathon Edition – Post-Mentorship)  
* **Date:** April 15, 2026  
* **Project Name:** UniOps – Small OS for Operations  
* **Hackathon:** DevOps Hackathon (Reva University – Team 07\)

**Hackathon Duration:** 28 hours (compressed from original 36-hour plan)

---

### **1\. Executive Summary**

UniOps is an **agentic “Small OS for Operations”** purpose-built for DevOps/SRE teams to eliminate toil and drastically reduce cognitive load. It unifies fragmented operational knowledge — primarily Confluence/runbooks (single source of truth), GitHub PRs/changes, simulated incident data (ServiceNow-style), Slack threads, and tribal knowledge — into one transparent, auditable, human-controlled intelligent system.

* **Core Architecture (updated post-mentorship):**  
* Controller Kernel \+ Dynamic Swarms \+ **Native** Permission Gates (HITL-first) \+ Three-Tier Memory \+ Kairos

(Strong emphasis on **transparency** — full chain-of-thought \+ data-point citations — and **plug-and-play data sources** as advised by mentors.)

* **Vision (directly from mentor feedback):**

SREs/Platform Engineers ask natural-language questions (“Why did Redis latency spike last week?” or “Run the standard high-CPU runbook on service X safely”) → UniOps retrieves from Confluence/runbooks \+ GitHub history \+ simulated incidents → shows **live reasoning trace with exact sources** → proposes safe actions → **executes only after explicit human approval**.

* **Hackathon Goal (28-hour MVP):**

Deliver a fully functional, demo-ready product that clearly beats partial solutions (HolmesGPT, OpenSRE, Port.io, Rootly) in **knowledge unification, radical transparency, native human-in-the-loop safety**, and **realistic DevOps toil reduction**. Stack redesigned for lower cost and MVP stability (Milvus instead of Chroma; GraphRAG kept lightweight).

**Key Mentor-Driven Changes Incorporated:**

* Prioritize Confluence/runbooks as single source of truth \+ GitHub change history over pure Slack.  
* Simulate ServiceNow-style incidents for realism (not just GitHub Actions).  
* Strong focus on **transparency** (chain-of-thought \+ data points used).  
* **Native HITL** Permission Gate (no non-native implementation).  
* Vector store switched to **Milvus** (enterprise-ready; Chroma risk noted by Mentor 2).  
* Plug-and-play data source philosophy.  
* Acknowledge tribal knowledge exists (\~10% of enterprises) but is secondary.  
  ---

  ### **2\. Problem Statement (Source of Truth: Mentorship Transcript)**

Engineering teams (especially SREs/DevOps) lose hours daily because:

* Operational knowledge lives in Confluence (single source), runbooks/playbooks, GitHub PRs, Slack threads, and occasional tribal knowledge (forgotten fixes).  
* Context switching between tools is painful even when documentation exists.  
* Incident response often requires hunting history of changes, feature flags, or customer-specific customizations.  
* Existing tools are either telemetry-heavy or lack deep multi-agent reasoning \+ strong human-in-the-loop.  
* GitHub Actions alone is too ephemeral/limited; real value is in production incidents and change history.

Mentor insight: In well-documented teams, knowledge hunting is “very quick” for known errors, but still painful for new issues or customer-specific customizations. Tribal knowledge exists in \~10% of enterprises.

---

### **3\. Solution Overview**

**Core Metaphor:** UniOps is a lightweight “Small OS” running inside your engineering workspace.

* **Controller (Kernel)** → single entry point, spawns swarms, enforces native safety.  
* **Dynamic Swarms** → Retrieval, Reasoning, Execution agents working in parallel.  
* **Native Permission Gate** → every external action requires explicit human approval \+ full audit trail \+ chain-of-thought visibility.  
* **Three-Tier Memory** → MEMORY.MD index → Markdown runbooks/Confluence → JSON transcripts.  
* **Kairos (autoDream)** → background agent that maintains memory hygiene and deduplication.  
* **Live Reasoning Trace** → real-time SSE stream showing every thought → tool → observation \+ exact data sources cited.  
* **Frontend** → clean Next.js chat \+ trace panel \+ approval modal.

**Post-Mentorship Focus:** Plug-and-play data ingestion (Confluence \+ GitHub \+ simulated incidents first) and radical transparency so engineers can trust (and audit) every conclusion.

---

### **4\. Key Features (MVP Scope for 28h)**

**Must-have (Demo-ready)**

1. Natural language query interface  
2. **Live reasoning trace (SSE)** with full chain-of-thought \+ source citations  
3. Retrieval from ingested Confluence-style runbooks \+ GitHub PRs \+ sample Slack \+ simulated ServiceNow incidents  
4. Multi-agent swarm orchestration (Controller → Swarms)  
5. **Native** Permission Gate \+ Human approval modal for every action  
6. Safe mock tool execution (GitHub PR comment/create rollback, Slack post, Jira update)  
7. Three-Tier Memory with basic Kairos (deduplication)  
8. Audit log of every agent step \+ data sources used

**Nice-to-have (if time)**

* Lightweight Neo4j graph for service/feature-flag dependencies (Phase 2\)  
* One-click “ingest new runbook/Confluence page” button  
* Plug-and-play data source demo (show how to add Grafana/ServiceNow)  
  ---

  ### **5\. Target Users & Use Cases (Mentor-Validated Demo Flows)**

**Primary User:** SRE / Platform Engineer / On-call Developer

**Key Use Cases (Demo Flows – directly inspired by transcript):**

1. “Explain the high Redis latency incident from last week” (pulls from Confluence runbook \+ GitHub changes \+ simulated incident)  
2. “Run the standard high-CPU runbook on service X” (retrieves runbook, shows steps, asks for approval before any mock execution)  
3. “Create a rollback PR for the last deployment, post to Slack, and update Jira” (full human approval flow \+ audit)  
4. “Summarise tribal knowledge \+ Confluence notes from recent Slack thread about customer XYZ feature flag”  
   ---

   ### **6\. Technical Architecture (High-Level – Redesigned per Mentor 2\)**

* **Frontend:** Next.js 15 (App Router) \+ Tailwind \+ shadcn/ui \+ EventSource (SSE)  
* **Backend:** FastAPI \+ Python 3.12  
* **Orchestration:** Custom Small OS (Controller \+ Swarms) on LangGraph patterns  
* **LLM:** Groq (primary) \+ Apfel local fallback (M1)  
* **Knowledge Layer:** LlamaIndex \+ **Milvus** (vector store – replaced Chroma per mentor advice) \+ SimpleDirectoryReader for markdown/Confluence export  
* **Memory:** Three-tier system \+ Common Swarm Memory  
* **Safety:** **Native** PermissionGate \+ approval queue (HITL-first)  
* **Observability:** SSE live trace \+ structured audit logs (every data point cited)

**Cost & Stability Note:** Hybrid GraphRAG kept lightweight. Milvus chosen for enterprise-readiness and to avoid Chroma \+ GraphRAG breakage risk highlighted by Mentor 2\.

---

### **7\. Phase-Wise Implementation Plan (28-Hour Hackathon)**

**Team Roles (finalised post-mentorship):**

* **Chirag DS** – Overall \+ Backend \+ Agents \+ Memory \+ Orchestration  
* **Dhruva** – Frontend \+ SSE \+ UI polish \+ Approval Modal  
* **Srinidhi** – Data ingestion \+ Testing \+ PPT/Demo video \+ Milvus setup

  #### **Phase 0: Setup & Monorepo (0–2 hours)**

* Monorepo: uniops/ (frontend/, backend/, data/, src/)  
* Next.js 15 \+ Tailwind \+ shadcn/ui  
* FastAPI \+ uv/venv \+ requirements.txt  
* .env.example, docker-compose.yml  
* **Milvus** persistent storage \+ sample data (data/runbooks/, data/incidents/, data/confluence/)  
* Groq \+ Apfel config  
* **Deliverable:** docker-compose up shows empty chat UI

  #### **Phase 1: Core Small OS Foundation (2–6 hours)**

* src/controller/controller.py (Kernel)  
* src/memory/three\_tier\_memory.py \+ memory\_index.py  
* src/gates/permission\_gate.py (**native HITL**)  
* Basic LangGraph state machine \+ step\_callback for live tracing  
* **Deliverable:** Kernel accepts query → returns structured plan with transparency

  #### **Phase 2: Swarms \+ Knowledge Layer (6–13 hours)**

* Three swarms: retrieval\_swarm.py, reasoning\_swarm.py, execution\_swarm.py  
* LlamaIndex \+ **Milvus** Hybrid retrieval (focus on Confluence \+ GitHub \+ simulated incidents)  
* Ingest sample data (5–6 markdown runbooks \+ GitHub examples \+ Slack \+ mock ServiceNow incidents)  
* **Deliverable:** End-to-end query → retrieval → transparent reasoning (mock execution)

  #### **Phase 3: Tools, Safety & Live Trace (13–20 hours)**

* Tool registry (src/tools/) – GitHub, Slack, Jira mocks  
* Full **native** Permission Gate \+ approval queue  
* FastAPI SSE endpoint (/chat/stream)  
* Frontend: Chat \+ ReasoningTrace (with citations) \+ ApprovalModal  
* Human-in-the-loop flow complete  
* **Deliverable:** Live trace visible \+ safe mock action approval

  #### **Phase 4: Polish \+ Kairos \+ Dashboard (20–25 hours)**

* Basic Kairos background agent (deduplication)  
* Enhanced dashboard with audit log \+ source citations  
* Error handling \+ local LLM fallback  
* Responsive UI \+ loading states  
* **Deliverable:** Polished, production-like UI

  #### **Phase 5: Testing, Demo & Submission (25–28 hours)**

* Run 4 mentor-validated demo flows end-to-end  
* Record 2-minute demo video  
* Finalise PPT (8–10 slides using htf.pptx template)  
* README with architecture diagram \+ one-click run instructions  
* Docker packaging  
* **Deliverable:** Ready-to-submit repo \+ demo video \+ PPT \+ differentiation table vs competitors  
  ---

  ### **8\. Non-Functional Requirements**

* **Safety:** Every external action **MUST** go through native Permission Gate \+ explicit human approval (mentor emphasis)  
* **Observability:** 100% of agent steps \+ data sources \+ chain-of-thought visible in live trace  
* **Performance:** \< 8 seconds to first reasoning step (Groq)  
* **Cost Awareness:** Stack redesigned per Mentor 2 feedback (Milvus \+ lightweight GraphRAG)  
* **Local-first:** Fully works with Apfel LLM (no internet required for demo)  
* **Plug-and-play:** Designed so new data sources (Grafana, ServiceNow, etc.) can be added easily  
  ---

  ### **9\. Success Criteria (Judges will love these)**

* Live demo shows natural language → visible chain-of-thought \+ source citations → human approval → mock action executed  
* Clear differentiation table vs HolmesGPT / OpenSRE / Port.io / Rootly (transparency \+ native HITL \+ Milvus-based unification)  
* **Transparency** is the star: engineers can see exactly which Confluence page, GitHub PR, or incident was used  
* Memory hygiene via Kairos (even if basic)  
* Clean, professional UI with real-time trace  
* Plug-and-play philosophy visibly demonstrated

