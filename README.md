# n8n webhook

AstrBot 插件, 用于触发并调用n8n webhook

AstrBot plugin for triggering and calling n8n webhooks.

# 支持
## 调用方法

> [!note]
> 目标会话标识可用/sid查看。/sid 指令返回的结果中的 SID 就是 umo 。

### **1. 发送消息**  
**Endpoint:**  
`POST https://your-n8n-domain.com/webhook/your-path`  

**Headers:**  
- `Authorization: Bearer <API_TOKEN>`  

**Request Body (JSON):**  
```json
{
  "content": "消息内容或base64编码的图片",
  "umo": "目标会话标识",
  "type": "可选，消息类型，默认为text，可选值：text, image",
  "callback_url": "可选，处理结果回调URL"
}
```

**Response:**  
```json
{
  "status": "queued",
  "message_id": "生成的消息ID",
  "queue_size": 1
}
```

---
