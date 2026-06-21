import prompt
import model
from tools import registry
import json
import re

def call_agent(query:str):
    messages=[{"role": "system", "content": prompt.system_prompt(registry.describe())},{"role": "user", "content": query}]
    llm_client = model.get_model()
    for _ in range(5):
        reply = llm_client.chat(messages=messages)
        final_m  = re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)
        action_m = re.search(r"Action:\s*(.+)", reply)
        input_m  = re.search(r"Action Input:\s*(.+)", reply)
        if final_m:
            return final_m.group(1).strip()

        if action_m and input_m:
            action = action_m.group(1).strip()
            action_input = input_m.group(1).strip()
            try:
                args = json.loads(action_input)
                observation = registry.call(action, **args)
            except Exception as e:
                observation = f"Error: {e}"
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role":"user", "content": f"Observation: {observation}"})

    return "Stopped: reached max iterations."

        