from fastmcp import FastMCP
import requests

def get_weather(adcode: str) -> dict:
    """获取指定城市的天气信息"""
    mcp = FastMCP()
    api_key = mcp.config.weather_sse.env.API_KEY
    if not api_key:
        raise ValueError("未提供API_KEY")
    
    url = f"https://restapi.amap.com/v3/weather/weatherInfo?city={adcode}&key={api_key}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def main():
    try:
        weather_data = get_weather("310000")  # 上海的adcode
        if weather_data["status"] == "1":
            lives = weather_data["lives"][0]
            print(f"上海天气信息：")
            print(f"温度：{lives['temperature']}℃")
            print(f"天气：{lives['weather']}")
            print(f"风向：{lives['winddirection']}")
            print(f"风力：{lives['windpower']}")
            print(f"湿度：{lives['humidity']}%")
            print(f"发布时间：{lives['reporttime']}")
        else:
            print(f"获取天气信息失败：{weather_data['info']}")
    except Exception as e:
        print(f"发生错误：{str(e)}")

if __name__ == "__main__":
    main()
