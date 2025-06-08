# n8n webhook

AstrBot 插件, 用于触发并调用n8n webhook

AstrBot plugin for triggering and calling n8n webhooks.

# 支持
## 调用方法

> [!note]
> 在对话中使用`/n8n`触发调用n8n, 比如`/n8n ob:#创意 #想法 #日志 可以做一个n8n的插件` 则会调用n8n webhook,内容是
> ```json
{
  "message": "ob:#创意 #想法 #日志 可以做一个n8n的插件",
  "senderName": "somebody"
}
> ```

### **1. 配置当前插件(同时配置n8n webhook)**  
**Endpoint:**  
`POST https://your-n8n-domain.com/webhook/your-path`  

**Basic Auth:**  
- `username: 'username-you-need-change'`
- `password: 'password-you-need-change'`

**Request Body (JSON):**  
```json
{
  "message": "消息内容或base64编码的图片",
  "senderName": "消息发送人"
}
```

**Response:**  
```json
{
  "success": true,
  "data": "n8n响应的message"
}
```
---
