import { Injectable } from '@angular/core'
import { HttpClient } from '@angular/common/http'
import { Router, ActivatedRoute } from '@angular/router'
import { BehaviorSubject, Observable } from 'rxjs'

import { MessageService } from 'primeng/api'

import { UsersService } from './backend/api/users.service'

@Injectable({
    providedIn: 'root',
})
export class AuthService {
    private currentSessionSubject: BehaviorSubject<any>
    public currentSession: Observable<any>
    public session: any

    constructor(
        private http: HttpClient,
        private api: UsersService,
        private router: Router,
        private msgSrv: MessageService
    ) {
        const session = localStorage.getItem('session')
        if (session) {
            this.session = JSON.parse(session)
        } else {
            this.session = null
        }

        this.currentSessionSubject = new BehaviorSubject(this.session)
        this.currentSession = this.currentSessionSubject.asObservable()
    }

    login(user, password, returnUrl) {
        const credentials = { user, password }
        this.api.login(credentials).subscribe(
            (data) => {
                this.session = data

                if (this.session === null) {
                    this.deleteLocalSession()
                    this.msgSrv.add({
                        severity: 'error',
                        summary: 'Invalid user or password',
                    })
                    return
                }

                this.currentSessionSubject.next(this.session)
                localStorage.setItem('session', JSON.stringify(this.session))
                // this.router.navigate([returnUrl])
            },
            (err) => {
                let msg = err.statusText
                if (err.error && err.error.detail) {
                    msg = err.error.detail
                }
                this.msgSrv.add({
                    severity: 'error',
                    summary: 'Login erred',
                    detail: 'Login erred: ' + msg,
                    life: 10000,
                })
            }
        )
    }

    logout() {
        if (this.session && this.session.id) {
            this.api.logout(this.session.id).subscribe(
                (resp) => {
                    this.deleteLocalSession()
                },
                (err) => {
                    this.deleteLocalSession()
                }
            )
        }
    }

    deleteLocalSession() {
        this.session = null
        localStorage.removeItem('session')
        this.currentSessionSubject.next(null)
    }

    public hasPermission(permName) {
        if (this.session && this.session.user.user === 'demo') {
            return false
        }
        return true
    }

    public permTip(permName) {
        if (!this.hasPermission(permName)) {
            return 'no permission to invoke this action'
        }
        return ''
    }
}
