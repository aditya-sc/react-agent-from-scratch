from agent import call_agent

def main():
    # chatbot_response = model.get_model().chat("what is captial of france?", "t1")
    # print(chatbot_response)
    # print(registry.describe())
    # print(registry.call("get_crypto_price", crypto_id="bitcoin"))
    # print(registry.call("get_bank_details_from_ifsc", ifsc="ICIC0000956"))
     print(call_agent("What is the price of bitcoin in USD?"))

if __name__ == "__main__":
    main()
