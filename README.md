# n8n webhook

AstrBot 插件, 用于触发并调用n8n webhook

AstrBot plugin for triggering and calling n8n webhooks.

# 支持
## 调用方法

> [!note]
> 在对话中使用`/n8n`触发调用n8n, 比如`/n8n ob:#创意 #想法 #日志 可以做一个n8n的插件`

### **1. 发送消息**  
**Endpoint:**  
`POST https://your-n8n-domain.com/webhook/your-path`  

**Basic Auth:**  
- `username: 'username-you-need-change'`
- `password: 'password-you-need-change'`

**Request Body (JSON):**  
```json
{
  "content": "消息内容或base64编码的图片",
  "umo": "目标会话标识",
  "type": "可选，消息类型，默认为text，可选值：text, image",
  "from": "from-id"
}
```

**Response:**  
```json
{
  "success": true,
  "message": "n8n响应的message",
  "handledBy": "obsidian"
}
```

---
