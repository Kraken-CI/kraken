import { Injectable } from '@angular/core'
import { Router } from '@angular/router'
import {
    HttpRequest,
    HttpHandler,
    HttpEvent,
    HttpInterceptor,
} from '@angular/common/http'

import { Observable } from 'rxjs'
import { tap } from 'rxjs/operators'

import { AuthService } from './auth.service'

@Injectable()
export class AuthInterceptor implements HttpInterceptor {
    constructor(private router: Router, private auth: AuthService) {}

    intercept(
        request: HttpRequest<unknown>,
        next: HttpHandler
    ): Observable<HttpEvent<unknown>> {
        if (this.auth.session && this.auth.session.token) {
            const userToken = this.auth.session.token
            const modifiedReq = request.clone({
                headers: request.headers.set(
                    'Authorization',
                    `Bearer ${userToken}`
                ),
            })
            return next.handle(modifiedReq).pipe(
                tap(
                    (resp) => {},
                    (error) => {
                        if (error.status === 401) {
                            this.auth.deleteLocalSession()
                        }
                    }
                )
            )
        } else {
            return next.handle(request)
        }
    }
}
