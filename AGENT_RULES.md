# AGENT_RULES.md — قرار | Qarar AI

## Mandatory Engineering Rules

1. **Zero Breaking Changes:** Never break existing working features (`Resources`, `Orders`, `Stock`, Gantt chart, OR-Tools solver).
2. **Universal Plug & Play Architecture:** Keep the engine 100% generic; never hardcode industry-specific names inside the solver logic.
3. **Auto-Test Before Finishing:** Verify syntax and runtime so Streamlit runs with zero errors.
4. **Auto-Git Commit & Push:** Stage and commit all changes after every task (`git add . && git commit -m "..."`).
5. **Mandatory Arabic Mini-Report:** End EVERY response with a concise Arabic Mini-Report showing:
   - ✅ ما تم إنجازه
   - 🧪 حالة الاختبار
   - 🔗 حالة Git والربط بـ GitHub
   - ⏭️ الخطوة المقترحة التالية
