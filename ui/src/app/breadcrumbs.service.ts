import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class BreadcrumbsService {

    private crumbs = new BehaviorSubject([{
            label: 'Home',
            url: '/',
            id: 0
        }]);

    constructor() { }

    setCrumbs(crumbs) {
        this.crumbs.next(crumbs);
    }

    getCrumbs() {
        return this.crumbs.asObservable();
    }
}
