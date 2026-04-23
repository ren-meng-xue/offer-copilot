# -*- coding: utf-8 -*-
"""
Time           : 2026/4/22 08:58
Author         : xuebao
File           : enums.py
"""


import enum

class UserStatus(str,enum.Enum):
    """用户状态枚举类，这里的状态就是生命周期，他们解决的是不同层级的问题"""
    ACTIVE="active"#活跃状态，用户可以正常登录和使用账户
    LOCKED="locked"#锁定状态，用户被管理员锁定或因多次登录失败被系统锁定，无法登录账户
    PENDING_VERIFY = "pending_verify" #待验证状态，用户注册后需要验证邮箱或手机号才能激活账户