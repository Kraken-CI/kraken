import { Injectable } from '@angular/core'
import { HttpClient } from '@angular/common/http'
import { Router } from '@angular/router'

import { BehaviorSubject, Observable } from 'rxjs'
import { CookieService } from 'ngx-cookie-service'

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
        private cookieService: CookieService
    ) {
        const session = localStorage.getItem('session')
        if (session) {
            this.session = JSON.parse(session)
            this.cookieService.set('kk_session_token', this.session.token)
        } else {
            this.session = null
        }
        if (this.session === null) {
            let token = this.cookieService.get('kk_session_token')
            if (token) {
                this.getSession(token)
            }
        }

        this.currentSessionSubject = new BehaviorSubject(this.session)
        this.currentSession = this.currentSessionSubject.asObservable()
    }

    saveLocalSession() {
        this.currentSessionSubject.next(this.session)
        localStorage.setItem('session', JSON.stringify(this.session))
        this.cookieService.set('kk_session_token', this.session.token)
    }

    login(user, password, returnUrl) {
        return new Observable((observer) => {
            const credentials = { user, password }
            this.api.login(credentials).subscribe(
                (data) => {
                    this.session = data

                    if (this.session === null) {
                        this.deleteLocalSession()
                        observer.next({
                            severity: 'error',
                            summary: 'Invalid user or password',
                        })
                        return
                    }

                    this.saveLocalSession()
                    // this.router.navigate([returnUrl])
                    observer.next(null)
                },
                (err) => {
                    let msg = err.statusText
                    if (err.error && err.error.detail) {
                        msg = err.error.detail
                    }
                    observer.next({
                        severity: 'error',
                        summary: 'Login erred',
                        detail: msg,
                        life: 10000,
                    })
                }
            )
        })
    }

    loginWith(idProvider) {
        const data = { method: 'oidc', oidc_provider: idProvider }
        this.api.login(data).subscribe(
            (data) => {
                window.location.href = data['redirect_url']
            },
            (err) => {
                let msg = err.statusText
                if (err.error && err.error.detail) {
                    msg = err.error.detail
                }
                // observer.next({
                //     severity: 'error',
                //     summary: 'Login erred',
                //     detail: msg,
                //     life: 10000,
                // })
            }
        )
    }

    getSession(token) {
        this.session = { token: token }
        this.api.getSession(token).subscribe(
            (data) => {
                this.session = data
                this.saveLocalSession()
                // this.router.navigate([returnUrl])
            },
            (err) => {
                this.deleteLocalSession()
            }
        )
    }

    logout() {
        if (this.session && this.session.token) {
            this.api.logout(this.session.token).subscribe(
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
        this.cookieService.delete('kk_session_token')
        this.currentSessionSubject.next(null)
    }

    public hasPermission(projectId, expectedRole) {
        if (!this.session.roles) {
            this.logout()
        }

        if (this.session.roles.superadmin) {
            return true
        }
        if (projectId === null) {
            return false
        }

        if (!this.session.roles.projects[projectId]) {
            return false
        }

        let sufficientRoles = []
        if (expectedRole === 'admin') {
            sufficientRoles = ['admin']
        } else if (expectedRole === 'pwrusr') {
            sufficientRoles = ['admin', 'pwrusr']
        } else if (expectedRole === 'viewer') {
            sufficientRoles = ['admin', 'pwrusr', 'viewer']
        }
        let roleInProj = this.session.roles.projects[projectId]
        if (sufficientRoles.includes(roleInProj)) {
            return true
        }

        return false
    }

    public permTip(projectId, roleName) {
        if (!this.hasPermission(projectId, roleName)) {
            return 'no permission to invoke this action'
        }
        return ''
    }
}
