import requests

class ToolRegistry:
    def __init__(self):
        self._tools={}

    def register(self, fn):
        self._tools[fn.__name__] = {"fn": fn, "description": fn.__doc__}

    def call(self, name, **kwargs):
        return self._tools[name]["fn"](**kwargs)

    def describe(self) -> str:
        tool_lst = f"List of available tools: {"|".join(f"{name}:{meta["description"]}" for name, meta in self._tools.items())}"
        return tool_lst



def get_bank_details_from_ifsc(ifsc:str) -> dict:
    """Get bank details of banks in India using their IFSC Code
        Args:
            ifsc: ifsc code of the bank
    """
    url = f"https://ifsc.razorpay.com/{ifsc}"
    response = requests.get(url=url)
    response.raise_for_status()
    return response.json()

def get_crypto_price(crypto_id:str, currency:str="usd") -> str:
    """Fetch real-world crypto currency pricing in any currency
        Args:
            crypto_id: CoinGecko's explicit, internal API ID string format of the crypto currecny
            currency: currency in which price is to be shown
    """
    url = "https://api.coingecko.com/api/v3/simple/price"
    query_parameters = {
        "ids": crypto_id,
        "vs_currencies": currency
    }
    response = requests.get(url=url, params=query_parameters)
    response.raise_for_status()
    return response.json()[crypto_id][currency]

registry = ToolRegistry()
registry.register(get_bank_details_from_ifsc)
registry.register(get_crypto_price)